"""
migrate_add_skill_artifact_types.py — adds skill_artifact_types mapping table to routing.db.

Idempotent: CREATE TABLE IF NOT EXISTS + INSERT OR IGNORE for seed rows.
Safe to re-run — no duplicates, no errors.

Design (task vschk-platform--514 block 406 decision-07):
- Skills produce multiple artifact_type values (plan-first produces plan-first + report + user-note)
- Some artifact_types are shared (research-doc between arch-first and audit-first)
- Naive JOIN on artifact_type = skill.name misses orchestrator skills entirely
- Mapping table with weights = MVP fix; invocation log (block 407) = ground truth

Seed rows:
- Direct-match (weight=1.0): skill_name == artifact_type for protocol skills
- Orchestrator attributions (weight=1.0 exclusive): ship-first → report/user-note; audit-first → audit-doc/variants; arch-first → arch-doc/variants
- Shared (weight=0.5): research-doc split between arch-first and audit-first

Run:
    python3 scripts/migrate_add_skill_artifact_types.py [db_path]
    DB_PATH=/path/to/routing.db python3 scripts/migrate_add_skill_artifact_types.py
"""

from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path

DEFAULT_DB = str(Path.home() / "Projects/vschk-platform/tasks/routing.db")

# (skill_name, artifact_type, weight)
SEED_ROWS = [
    # ── Direct-match protocol skills (weight 1.0) ───────────────────────
    ("plan-first",     "plan-first",       1.0),
    ("flow-first",     "flow-first",       1.0),
    ("library-first",  "library-first",    1.0),
    ("idea-first",     "idea-first",       1.0),
    ("decision-first", "decision-first",   1.0),
    ("decision-first", "decision",         1.0),
    ("habit-first",    "habit-first",      1.0),
    ("note-first",     "note",             1.0),
    ("note-first",     "note-first",       1.0),
    ("ui-ai-first",    "ui-ai-first",      1.0),
    ("ui-ai-first",    "ui-ai-first-sub",  1.0),
    ("ui-ai-first",    "ui-ai-first-audit", 1.0),

    # ── ship-first orchestrator (writes report + user-note per block) ───
    ("ship-first",     "report",           1.0),
    ("ship-first",     "user-note",        1.0),
    ("ship-first",     "user-note-final",  1.0),
    ("ship-first",     "closure-report",   1.0),
    ("ship-first",     "closure-note",     1.0),

    # ── audit-first orchestrator (produces audit-doc + variants) ────────
    ("audit-first",    "audit-doc",        1.0),
    ("audit-first",    "audit-inclusion",  1.0),
    ("audit-first",    "audit-preliminary", 1.0),
    ("audit-first",    "audit-report",     1.0),
    ("audit-first",    "audit-table",      1.0),
    ("audit-first",    "acceptance-audit", 1.0),

    # ── arch-first orchestrator (produces arch-doc + architecture) ──────
    ("arch-first",     "arch-first",       1.0),
    ("arch-first",     "arch-doc",         1.0),
    ("arch-first",     "architecture",     1.0),
    ("arch-first",     "architecture-design", 1.0),
    ("arch-first",     "architecture-map", 1.0),
    ("arch-first",     "design-doc",       1.0),

    # ── Shared: research-doc split arch/audit ────────────────────────────
    ("arch-first",     "research-doc",     0.5),
    ("audit-first",    "research-doc",     0.5),

    # ── check-first orchestrator (writes decision + gaps) ────────────────
    ("check-first",    "check-backend",    1.0),
    ("check-first",    "check-modes",      1.0),
    ("check-first",    "check-ui",         1.0),

    # ── cadence-first ───────────────────────────────────────────────────
    ("cadence-first",  "cadence-decision", 1.0),

    # ── chain-* orchestration (produces chain-doc + variants) ────────────
    ("chains-from-atoms", "chain-doc",     1.0),
    ("chain-build",    "chain-migration",  1.0),
    ("chain-build",    "chain-template-row", 1.0),
    ("chain-validate", "chain-compliance", 1.0),
    ("chain-diagnose-failure", "diagnostic", 1.0),

    # ── atoms/atom-* ─────────────────────────────────────────────────────
    ("atoms-from-spec", "atoms-table",     1.0),
    ("atom-build",     "atom-handler",     1.0),
    ("atom-build",     "atom-register",    1.0),
    ("atom-build",     "atom-spec",        1.0),
    ("atom-build",     "atom-fixture",     1.0),
    ("atom-check-compliance", "atom-compliance", 1.0),
]


def migrate(db_path: str) -> None:
    print(f"DB: {db_path}")
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # CREATE TABLE (idempotent)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS skill_artifact_types (
            skill_name    TEXT NOT NULL,
            artifact_type TEXT NOT NULL,
            weight        REAL NOT NULL DEFAULT 1.0,
            PRIMARY KEY (skill_name, artifact_type)
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_sat_skill ON skill_artifact_types(skill_name)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_sat_artifact_type ON skill_artifact_types(artifact_type)")

    # Seed rows
    inserted = 0
    for row in SEED_ROWS:
        cur.execute(
            "INSERT OR IGNORE INTO skill_artifact_types (skill_name, artifact_type, weight) VALUES (?, ?, ?)",
            row,
        )
        if cur.rowcount:
            inserted += 1

    conn.commit()

    total = cur.execute("SELECT COUNT(*) FROM skill_artifact_types").fetchone()[0]
    unique_skills = cur.execute("SELECT COUNT(DISTINCT skill_name) FROM skill_artifact_types").fetchone()[0]

    print(f"Seed rows attempted: {len(SEED_ROWS)}")
    print(f"Inserted this run:   {inserted}")
    print(f"Total in table:      {total}")
    print(f"Unique skills:       {unique_skills}")
    conn.close()


if __name__ == "__main__":
    db = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("DB_PATH", DEFAULT_DB)
    migrate(db)
