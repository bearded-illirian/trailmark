"""
db.py — Read-only access to routing.db.

Never writes. Uses PRAGMA query_only=1 as a belt-and-braces guard.
Consumers: FastAPI endpoints in Block 3.
"""

from __future__ import annotations

import re
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator, Optional


# ── Types ────────────────────────────────────────────────────────────────

TASK_TYPES_DEFAULT = ("task", "fast-track", "brief", "tz", "epic")


@dataclass
class Task:
    id: str
    type: str
    project: Optional[str]
    title: Optional[str]
    status: str
    number: Optional[int]
    domain: str
    created_at: Optional[str]
    closed_at: Optional[str]
    file_path: Optional[str]


@dataclass
class Block:
    block_num: int
    title: Optional[str]
    status: str
    source: Optional[str]
    commit_hash: Optional[str]
    atom_type: Optional[str]
    parent_block_num: Optional[int]
    type: str
    sort_order: Optional[int]


@dataclass
class Artifact:
    block_num_raw: str
    block_num_int: Optional[int]
    round_num: Optional[int]
    artifact_type: Optional[str]
    file_name: Optional[str]
    file_path: Optional[str]
    created_by: Optional[str]
    created_at: Optional[str]


@dataclass
class TaskDetail:
    task: Task
    blocks: list[Block] = field(default_factory=list)
    artifacts: list[Artifact] = field(default_factory=list)


@dataclass
class Deploy:
    id: int
    project: str
    commit_sha: str
    deployed_at: str
    status: str
    ref_name: Optional[str]
    commit_msg: Optional[str]
    task_id: Optional[str]
    # display-only string — task_blocks stores mixed types (int, float, 'Y1.1', etc)
    block_num: Optional[str]
    raw_log: Optional[str] = None
    task_title: Optional[str] = None


# ── Helpers ──────────────────────────────────────────────────────────────

_BLOCK_NUM_RE = re.compile(r"^(\d+)")


def _parse_block_num(raw: str | None) -> Optional[int]:
    """
    task_artifacts.block_num is TEXT with values like '1', '2.3', 'D2.5'.
    Extract leading integer for grouping; None for non-numeric prefixes.
    """
    if raw is None:
        return None
    m = _BLOCK_NUM_RE.match(str(raw).strip())
    return int(m.group(1)) if m else None


@contextmanager
def _connect(db_path: Path) -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA query_only = 1")
        yield conn
    finally:
        conn.close()


# ── Queries ──────────────────────────────────────────────────────────────

def list_tasks(
    db_path: Path,
    project_id: Optional[str] = None,
    types: Optional[tuple[str, ...]] = None,
    limit: int = 200,
) -> list[Task]:
    types = types or TASK_TYPES_DEFAULT
    placeholders = ",".join("?" * len(types))
    sql = (
        f"SELECT id, type, project, title, status, number, domain, "
        f"created_at, closed_at, file_path FROM artifacts "
        f"WHERE type IN ({placeholders})"
    )
    params: list = list(types)
    if project_id:
        sql += " AND project = ?"
        params.append(project_id)
    sql += " ORDER BY COALESCE(number, 0) DESC, created_at DESC LIMIT ?"
    params.append(limit)
    with _connect(db_path) as conn:
        rows = conn.execute(sql, params).fetchall()
    return [Task(**dict(r)) for r in rows]


def get_task(db_path: Path, task_id: str) -> Optional[Task]:
    sql = (
        "SELECT id, type, project, title, status, number, domain, "
        "created_at, closed_at, file_path FROM artifacts WHERE id = ?"
    )
    with _connect(db_path) as conn:
        row = conn.execute(sql, (task_id,)).fetchone()
    return Task(**dict(row)) if row else None


def list_blocks(db_path: Path, task_id: str) -> list[Block]:
    sql = (
        "SELECT block_num, title, status, source, commit_hash, "
        "atom_type, parent_block_num, type, sort_order "
        "FROM task_blocks WHERE task_id = ? "
        "ORDER BY COALESCE(sort_order, block_num * 100), block_num"
    )
    with _connect(db_path) as conn:
        rows = conn.execute(sql, (task_id,)).fetchall()
    return [Block(**dict(r)) for r in rows]


def list_artifacts(db_path: Path, task_id: str) -> list[Artifact]:
    sql = (
        "SELECT block_num, round_num, artifact_type, file_name, "
        "file_path, created_by, created_at "
        "FROM task_artifacts WHERE task_id = ? "
        "ORDER BY created_at, id"
    )
    with _connect(db_path) as conn:
        rows = conn.execute(sql, (task_id,)).fetchall()
    result: list[Artifact] = []
    for r in rows:
        d = dict(r)
        raw = d.pop("block_num")
        result.append(
            Artifact(
                block_num_raw=str(raw) if raw is not None else "",
                block_num_int=_parse_block_num(raw),
                **d,
            )
        )
    return result


def list_deploys_grouped_by_project(db_path: Path, project_id: str) -> dict:
    """Return {tasks: [{id, title, count, deploys}], unlinked: [...]} for project.

    Grouped view — does NOT include raw_log (inflate protection).
    Task titles fall back to slug id when artifacts.title is NULL.
    """
    sql = (
        "SELECT d.id, d.project, d.commit_sha, d.deployed_at, d.status, "
        "d.ref_name, d.commit_msg, d.task_id, d.block_num, "
        "COALESCE(a.title, a.id) AS task_title, "
        "a.number AS task_number, a.status AS task_status "
        "FROM deploys d LEFT JOIN artifacts a ON a.id = d.task_id "
        "WHERE d.project = ? ORDER BY d.deployed_at DESC"
    )
    with _connect(db_path) as conn:
        rows = [dict(r) for r in conn.execute(sql, (project_id,)).fetchall()]

    tasks_map: dict[str, dict] = {}
    unlinked: list[Deploy] = []
    for r in rows:
        task_number = r.pop("task_number", None)
        task_status = r.pop("task_status", None)
        if r.get("block_num") is not None:
            r["block_num"] = str(r["block_num"])
        d = Deploy(**r)
        if d.task_id:
            grp = tasks_map.setdefault(
                d.task_id,
                {
                    "id": d.task_id,
                    "title": d.task_title or d.task_id,
                    "number": task_number,
                    "status": task_status,
                    "deploys": [],
                },
            )
            grp["deploys"].append(d)
        else:
            unlinked.append(d)

    tasks = []
    for tid, grp in tasks_map.items():
        deploys = grp["deploys"]
        deploys.sort(key=lambda x: x.deployed_at, reverse=True)
        tasks.append({
            "id": tid,
            "title": grp["title"],
            "number": grp["number"],
            "status": grp["status"],
            "count": len(deploys),
            "deploys": deploys,
        })
    # Sort 1:1 with list_tasks(): number DESC NULLS LAST, then title
    tasks.sort(key=lambda g: (g["number"] is None, -(g["number"] or 0), g["title"] or ""))
    return {"tasks": tasks, "unlinked": unlinked}


def list_deploys_for_task(db_path: Path, task_id: str) -> list[Deploy]:
    """Drill-down: all deploys for one task_id. Includes raw_log field."""
    sql = (
        "SELECT id, project, commit_sha, deployed_at, status, ref_name, "
        "commit_msg, task_id, block_num, raw_log "
        "FROM deploys WHERE task_id = ? ORDER BY deployed_at DESC"
    )
    with _connect(db_path) as conn:
        rows = conn.execute(sql, (task_id,)).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        if d.get("block_num") is not None:
            d["block_num"] = str(d["block_num"])
        result.append(Deploy(**d))
    return result


def read_artifact_file(file_path: str, workspace_root: Path, max_kb: int = 500) -> str:
    """
    Read artifact md file. file_path can be relative ('tasks/log/...') or absolute.
    Enforces workspace_root confinement + size cap.

    Legacy absolute paths from a peer machine (routing.db often stores
    absolute local paths from wherever it was written) are translated to
    workspace_root-relative via the 'tasks/' anchor.
    """
    p = Path(file_path)
    if not p.is_absolute():
        p = workspace_root / p
    resolved = p.resolve()
    root_resolved = workspace_root.resolve()
    if not resolved.is_relative_to(root_resolved):
        # Legacy absolute Mac path — try translation via 'tasks/' anchor
        parts = Path(file_path).parts
        if "tasks" in parts:
            idx = parts.index("tasks")
            candidate = workspace_root / Path(*parts[idx:])
            resolved = candidate.resolve()
        if not resolved.is_relative_to(root_resolved):
            raise ValueError(f"Path escapes workspace root: {file_path}")
    if not resolved.is_file():
        raise FileNotFoundError(f"Artifact not found: {resolved}")
    if resolved.stat().st_size > max_kb * 1024:
        return resolved.read_text(encoding="utf-8", errors="replace")[: max_kb * 1024] + "\n\n[…truncated]"
    return resolved.read_text(encoding="utf-8", errors="replace")
