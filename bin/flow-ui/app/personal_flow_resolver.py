"""
personal_flow_resolver.py — Cross-DB resolver для personal_flow-based partner shares.

Задача radar-os--660 block 9050 (Wave 9 pack 2 final).

Consumer: partners_api.py /tree + /file endpoints. Branch: если
partner_row['tenant_code'] IS NOT NULL AND PERSONAL_FLOW_RESOLVER_ENABLED —
resolver возвращает file list через share_files JOIN files в per-tenant
personal_flow.sqlite. Иначе partners_api goes legacy filesystem path.

MVP scope (block 9050):
  - Cross-DB SQLite reader (mode=ro) — open per-tenant personal_flow.sqlite
  - Resolve share files: magic_token → share_id → JOIN share_files → JOIN files
  - Feature flag PERSONAL_FLOW_RESOLVER_ENABLED (default enabled)

Deferred to future task (не в 9050 MVP scope):
  - Content proxy для inline rendering (blocked by libsodium encrypted OAuth
    в bus_credentials — Python не имеет vault decrypt key)
  - Solution: new proxy endpoint radar-os side с internal HMAC auth
  - MVP: /file endpoint возвращает native Drive webViewLink → client opens в Google Drive
"""

from __future__ import annotations

import os
import re
import sqlite3
from pathlib import Path
from typing import Optional

# Feature flag — env-controlled rollback
PERSONAL_FLOW_RESOLVER_ENABLED = os.getenv("PERSONAL_FLOW_RESOLVER_ENABLED", "1") == "1"

# Per-tenant DB path prefix — read-only pattern (mode=ro)
# Matches server structure /srv/vschk/monolith-data/company/clients/{tenant}/personal_flow.sqlite
PERSONAL_FLOW_DB_ROOT = os.getenv(
    "PERSONAL_FLOW_DB_ROOT",
    "/srv/vschk/monolith-data/company/clients",
)

# Path traversal guard (matches radar-os upload.php pattern)
_TENANT_CODE_RE = re.compile(r"^[a-z0-9_-]+$")


def is_personal_flow_share(partner: dict) -> bool:
    """Check if partner row points to personal_flow share (not legacy filesystem)."""
    if not PERSONAL_FLOW_RESOLVER_ENABLED:
        return False
    tenant = partner.get("tenant_code")
    owner = partner.get("owner_employee_id")
    return bool(tenant) and owner is not None


def _open_personal_flow_db(tenant_code: str) -> Optional[sqlite3.Connection]:
    """Open per-tenant personal_flow.sqlite read-only. Returns None if invalid/missing."""
    if not _TENANT_CODE_RE.match(tenant_code):
        return None
    db_path = Path(PERSONAL_FLOW_DB_ROOT) / tenant_code / "personal_flow.sqlite"
    if not db_path.is_file():
        return None
    # SQLite URI syntax для read-only + immutable=0 (нам нужны свежие reads
    # из WAL, immutable=1 читал бы pre-checkpoint snapshot и мы могли бы не
    # увидеть только что записанный row от 9040 endpoint)
    uri = f"file:{db_path}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def resolve_share_files(partner: dict) -> Optional[list[dict]]:
    """
    Resolve list of files для personal_flow share by magic_token.

    Args:
        partner: partners.db row dict с tenant_code + magic_token

    Returns:
        List[dict] с keys: provider, file_id, name, mime_type, web_view_link, sort_order
        None если resolver disabled OR не personal_flow share OR tenant DB missing
        [] если share не найден в personal_flow_external_shares
    """
    if not is_personal_flow_share(partner):
        return None

    tenant_code = partner["tenant_code"]
    magic_token = partner.get("magic_token")
    if not magic_token:
        return None

    conn = _open_personal_flow_db(tenant_code)
    if conn is None:
        return None

    try:
        cursor = conn.execute("""
            SELECT
                f.provider,
                f.id AS file_id,
                f.name,
                f.mime_type,
                f.web_view_link,
                f.size_bytes,
                sf.sort_order
            FROM personal_flow_external_shares s
            JOIN personal_flow_share_files sf ON sf.share_id = s.share_id
            JOIN files f ON f.provider = sf.provider AND f.id = sf.file_id
            WHERE s.magic_token = ?
              AND s.revoked_at IS NULL
              AND (s.expires_at IS NULL OR s.expires_at > datetime('now'))
            ORDER BY sf.sort_order, f.name
        """, (magic_token,))
        rows = [dict(r) for r in cursor.fetchall()]
        return rows
    finally:
        conn.close()


def get_share_file(partner: dict, provider: str, file_id: str) -> Optional[dict]:
    """
    Get single file metadata from personal_flow share (validated ownership).

    Ensures file belongs к this share (SELECT with JOIN на share_files) — не
    просто files table lookup (иначе path traversal возможен на other user files).

    Returns: dict с same keys as resolve_share_files, or None если not found/unauthorized.
    """
    if not is_personal_flow_share(partner):
        return None

    tenant_code = partner["tenant_code"]
    magic_token = partner.get("magic_token")
    if not magic_token or not provider or not file_id:
        return None

    conn = _open_personal_flow_db(tenant_code)
    if conn is None:
        return None

    try:
        cursor = conn.execute("""
            SELECT
                f.provider,
                f.id AS file_id,
                f.name,
                f.mime_type,
                f.web_view_link,
                f.size_bytes
            FROM personal_flow_external_shares s
            JOIN personal_flow_share_files sf ON sf.share_id = s.share_id
            JOIN files f ON f.provider = sf.provider AND f.id = sf.file_id
            WHERE s.magic_token = ?
              AND f.provider = ?
              AND f.id = ?
              AND s.revoked_at IS NULL
              AND (s.expires_at IS NULL OR s.expires_at > datetime('now'))
            LIMIT 1
        """, (magic_token, provider, file_id))
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()
