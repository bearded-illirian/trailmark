"""
migrate_add_skill_invocations.py — adds skill_invocations log table to routing.db.

Idempotent: CREATE TABLE IF NOT EXISTS + CREATE INDEX IF NOT EXISTS.
Safe to re-run — no errors, no duplicates.

Design (task vschk-platform--514 block 407 decision-07):
- Forward-only log — each skill invocation writes one row via bash-hook in SKILL.md
- Ground truth complement to skill_artifact_types mapping (Block 406)
- flow-ui _load_usage_map prefers invocation counts when > 0, mapping fallback otherwise
- Data initially empty, grows as skills are invoked in Claude Code sessions

Schema:
- id INTEGER PRIMARY KEY AUTOINCREMENT
- task_id TEXT (can be NULL if skill invoked standalone)
- block_num TEXT (mirrors task_artifacts.block_num TEXT convention)
- skill_name TEXT NOT NULL
- invoked_at TEXT NOT NULL (ISO 8601 via datetime('now'))

Indexes:
- idx_skill_invocations_name — GROUP BY skill_name queries
- idx_skill_invocations_at — recent-first ORDER BY

Run:
    python3 scripts/migrate_add_skill_invocations.py [db_path]
    DB_PATH=/path/to/routing.db python3 scripts/migrate_add_skill_invocations.py
"""

from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path

DEFAULT_DB = str(Path.home() / "Projects/vschk-platform/tasks/routing.db")


def migrate(db_path: str) -> None:
    print(f"DB: {db_path}")
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS skill_invocations (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id    TEXT,
            block_num  TEXT,
            skill_name TEXT NOT NULL,
            invoked_at TEXT NOT NULL
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_skill_invocations_name ON skill_invocations(skill_name)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_skill_invocations_at ON skill_invocations(invoked_at DESC)")

    conn.commit()

    total = cur.execute("SELECT COUNT(*) FROM skill_invocations").fetchone()[0]
    indexes = [r[0] for r in cur.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='skill_invocations'"
    ).fetchall()]

    print(f"Total rows: {total}")
    print(f"Indexes:    {indexes}")
    conn.close()


if __name__ == "__main__":
    db = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("DB_PATH", DEFAULT_DB)
    migrate(db)
