"""
access.py — Access log (habit tracking).

Separate SQLite from routing.db to keep insert-heavy work isolated.
Auto-creates DB + schema on first use.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


_SCHEMA = """
CREATE TABLE IF NOT EXISTS access_log (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  ts           DATETIME DEFAULT CURRENT_TIMESTAMP,
  project      TEXT,
  target_type  TEXT,
  target_id    TEXT
);
CREATE INDEX IF NOT EXISTS idx_access_ts       ON access_log(ts);
CREATE INDEX IF NOT EXISTS idx_access_project  ON access_log(project);
"""


@contextmanager
def _connect(db_path: Path) -> Iterator[sqlite3.Connection]:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    try:
        conn.executescript(_SCHEMA)
        yield conn
        conn.commit()
    finally:
        conn.close()


def log_access(db_path: Path, project: str | None, target_type: str, target_id: str) -> None:
    with _connect(db_path) as conn:
        conn.execute(
            "INSERT INTO access_log (project, target_type, target_id) VALUES (?, ?, ?)",
            (project, target_type, target_id),
        )


def _streak_days(conn: sqlite3.Connection) -> int:
    """
    Count consecutive days ending today with at least one access.
    Returns 0 if today has no access. Uses UTC via date(ts).
    """
    rows = conn.execute(
        "SELECT DISTINCT date(ts) AS d FROM access_log ORDER BY d DESC LIMIT 60"
    ).fetchall()
    days = [r[0] for r in rows]
    if not days:
        return 0
    from datetime import date, timedelta
    cursor = date.today()
    streak = 0
    for d in days:
        if d == cursor.isoformat():
            streak += 1
            cursor -= timedelta(days=1)
        else:
            break
    return streak


def get_stats(db_path: Path) -> dict:
    with _connect(db_path) as conn:
        today_count = conn.execute(
            "SELECT COUNT(*) FROM access_log WHERE date(ts) = date('now')"
        ).fetchone()[0]
        # Calendar week (Mon-Sun): shift so Mon=0, Sun=6, subtract to get Monday date
        week_calendar = conn.execute(
            "SELECT COUNT(*) FROM access_log "
            "WHERE date(ts) >= date('now', '-' || ((strftime('%w','now')+6)%7) || ' days')"
        ).fetchone()[0]
        # Rolling 7 days: 7×24 hours back from now
        week_views = conn.execute(
            "SELECT COUNT(*) FROM access_log WHERE ts > datetime('now', '-7 days')"
        ).fetchone()[0]
        streak_days = _streak_days(conn)
    return {
        "today_count": today_count,
        "week_calendar": week_calendar,
        "week_views": week_views,
        "streak_days": streak_days,
    }
