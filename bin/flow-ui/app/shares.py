"""
shares.py — Public external share registry for magic-link URLs.

Storage: separate SQLite (external_shares.db) — pattern from partners.py.
Not in routing.db (read-only source of truth for tasks/artifacts).
Not in partners.db (partners = trusted personal, shares = public wide-audience).

Schema:
  external_shares(id, code, title, description, token, folder_path,
                  created_at, expires_at, is_active, view_count, download_count)
  external_share_visits(id, share_id, visited_at, ip_address, user_agent, referer)
  external_share_downloads(id, share_id, downloaded_at, ip_address, user_agent, referer)

Access flow:
  URL /share/{token}/ → validate_token(token) → resolve folder → serve files.
  log_visit() called on each share page GET.
  log_download() called on each zip download click.
"""

from __future__ import annotations

import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterator, Optional


_SCHEMA = """
CREATE TABLE IF NOT EXISTS external_shares (
  id             INTEGER PRIMARY KEY AUTOINCREMENT,
  code           TEXT NOT NULL UNIQUE,
  title          TEXT NOT NULL,
  description    TEXT,
  token          TEXT NOT NULL UNIQUE,
  folder_path    TEXT NOT NULL,
  created_at     DATETIME DEFAULT CURRENT_TIMESTAMP,
  expires_at     DATETIME,
  is_active      INTEGER NOT NULL DEFAULT 1,
  view_count     INTEGER NOT NULL DEFAULT 0,
  download_count INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_shares_token ON external_shares(token) WHERE is_active=1;
CREATE INDEX IF NOT EXISTS idx_shares_code  ON external_shares(code);

CREATE TABLE IF NOT EXISTS external_share_visits (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  share_id     INTEGER NOT NULL REFERENCES external_shares(id) ON DELETE CASCADE,
  visited_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
  ip_address   TEXT,
  user_agent   TEXT,
  referer      TEXT
);
CREATE INDEX IF NOT EXISTS idx_visits_share_time ON external_share_visits(share_id, visited_at);
CREATE INDEX IF NOT EXISTS idx_visits_ip         ON external_share_visits(ip_address);

CREATE TABLE IF NOT EXISTS external_share_downloads (
  id             INTEGER PRIMARY KEY AUTOINCREMENT,
  share_id       INTEGER NOT NULL REFERENCES external_shares(id) ON DELETE CASCADE,
  downloaded_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
  ip_address     TEXT,
  user_agent     TEXT,
  referer        TEXT
);
CREATE INDEX IF NOT EXISTS idx_downloads_share_time ON external_share_downloads(share_id, downloaded_at);
"""


@contextmanager
def _connect(db_path: Path) -> Iterator[sqlite3.Connection]:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        conn.executescript(_SCHEMA)
        yield conn
        conn.commit()
    finally:
        conn.close()


def generate_token(nbytes: int = 32) -> str:
    """Generate URL-safe crypto token. secrets.token_urlsafe(32) = ~43 chars."""
    return secrets.token_urlsafe(nbytes)


def create_share(
    db_path: Path,
    code: str,
    title: str,
    folder_path: Optional[str] = None,
    description: Optional[str] = None,
    expires_at: Optional[str] = None,
    token: Optional[str] = None,
) -> dict:
    """Create a new external share. Returns dict with all fields including generated token."""
    tok = token or generate_token()
    folder = folder_path or code
    with _connect(db_path) as conn:
        conn.execute(
            "INSERT INTO external_shares (code, title, description, token, folder_path, expires_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (code, title, description, tok, folder, expires_at),
        )
        row = conn.execute(
            "SELECT * FROM external_shares WHERE code = ?", (code,)
        ).fetchone()
    return dict(row)


def get_share_by_token(db_path: Path, token: str) -> Optional[dict]:
    """Validate magic-link token. Returns share dict or None if invalid/inactive/expired."""
    with _connect(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM external_shares "
            "WHERE token = ? AND is_active = 1 "
            "  AND (expires_at IS NULL OR datetime(expires_at) > datetime('now'))",
            (token,),
        ).fetchone()
    return dict(row) if row else None


def get_share_by_code(db_path: Path, code: str) -> Optional[dict]:
    """Lookup by human-readable code (slug). Same active/expiry checks as token."""
    with _connect(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM external_shares "
            "WHERE code = ? AND is_active = 1 "
            "  AND (expires_at IS NULL OR datetime(expires_at) > datetime('now'))",
            (code,),
        ).fetchone()
    return dict(row) if row else None


def get_share_by_token_or_code(db_path: Path, ident: str) -> Optional[dict]:
    """Resolve share by either token or code — enables /share/{nice-slug}/ URLs alongside /share/{token}/."""
    return get_share_by_token(db_path, ident) or get_share_by_code(db_path, ident)


def list_shares(db_path: Path, include_inactive: bool = False) -> list[dict]:
    """List all shares. Admin use only — never expose via public API."""
    with _connect(db_path) as conn:
        if include_inactive:
            rows = conn.execute(
                "SELECT * FROM external_shares ORDER BY created_at DESC"
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM external_shares WHERE is_active = 1 ORDER BY created_at DESC"
            ).fetchall()
    return [dict(r) for r in rows]


def deactivate_share(db_path: Path, code: str) -> None:
    """Soft-delete share. Token becomes invalid immediately."""
    with _connect(db_path) as conn:
        conn.execute("UPDATE external_shares SET is_active = 0 WHERE code = ?", (code,))


def regenerate_token(db_path: Path, code: str) -> str:
    """Regenerate magic token for existing share. Old token becomes invalid."""
    new_token = generate_token()
    with _connect(db_path) as conn:
        conn.execute(
            "UPDATE external_shares SET token = ? WHERE code = ?", (new_token, code)
        )
    return new_token


def log_visit(
    db_path: Path,
    share_id: int,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    referer: Optional[str] = None,
) -> None:
    """Log a share page visit. Atomic INSERT into visits + UPDATE view_count counter."""
    with _connect(db_path) as conn:
        conn.execute(
            "INSERT INTO external_share_visits (share_id, ip_address, user_agent, referer) "
            "VALUES (?, ?, ?, ?)",
            (share_id, ip_address, user_agent, referer),
        )
        conn.execute(
            "UPDATE external_shares SET view_count = view_count + 1 WHERE id = ?",
            (share_id,),
        )


def log_download(
    db_path: Path,
    share_id: int,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    referer: Optional[str] = None,
) -> None:
    """Log a zip download. Atomic INSERT into downloads + UPDATE download_count counter."""
    with _connect(db_path) as conn:
        conn.execute(
            "INSERT INTO external_share_downloads (share_id, ip_address, user_agent, referer) "
            "VALUES (?, ?, ?, ?)",
            (share_id, ip_address, user_agent, referer),
        )
        conn.execute(
            "UPDATE external_shares SET download_count = download_count + 1 WHERE id = ?",
            (share_id,),
        )
