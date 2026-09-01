"""
galaxy.py — Read-only endpoint powering the 3D workspace visualization.

Two loading modes:
  level=1  → 12 projects + task-level artifacts + arch_ref crosslinks (~1500 nodes)
  level=2  → level 1 + all task_artifacts (~21K nodes total)

Consumers: GET /api/galaxy/graph.json in main.py; frontend at /galaxy renders
the payload with 3d-force-graph.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

import yaml


TASK_LEVEL_TYPES = (
    "task", "fast-track", "epic", "brief", "tz", "audit", "arch", "backlog"
)

FALLBACK_COLOR = "#888888"


@contextmanager
def _open(db_path: Path) -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA query_only = 1")
        yield conn
    finally:
        conn.close()


def _load_brand_colors(projects_yml: Path) -> dict[str, dict[str, str]]:
    """
    Read projects.yml, return {project_id: {name, color, domain}} for active projects.
    Fallback color for projects without brand.primary → FALLBACK_COLOR.
    """
    with open(projects_yml, encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    out: dict[str, dict[str, str]] = {}
    for p in raw.get("projects", []):
        if p.get("status") != "active":
            continue
        pid = p.get("id")
        if not pid:
            continue
        brand = p.get("brand") or {}
        out[pid] = {
            "name": p.get("name") or pid,
            "color": (brand.get("primary") or FALLBACK_COLOR),
            "domain": p.get("domain") or "",
        }
    return out


def _tasks_placeholder_csv() -> str:
    return ",".join(f"'{t}'" for t in TASK_LEVEL_TYPES)


def _query_level1(conn: sqlite3.Connection, colors: dict[str, dict[str, str]]) -> tuple[list[dict], list[dict]]:
    """
    Level 1 = projects + task-level artifacts + arch_ref crosslinks.
    Returns (nodes, edges).
    """
    nodes: list[dict] = []
    edges: list[dict] = []

    # 1. Project nodes (from projects.yml, canonical) — only if they appear in artifacts
    used_projects = {
        r["project"]
        for r in conn.execute(
            f"SELECT DISTINCT project FROM artifacts WHERE project IS NOT NULL "
            f"AND type IN ({_tasks_placeholder_csv()})"
        )
    }
    for pid, meta in colors.items():
        if pid not in used_projects:
            continue
        nodes.append({
            "id": f"project:{pid}",
            "label": meta["name"],
            "type": "project",
            "project": pid,
            "color": meta["color"],
            "size": 40,
            "level": 0,
            "meta": {"domain": meta["domain"]},
        })

    # 2. Task-level artifact nodes
    task_rows = conn.execute(
        f"""SELECT id, type, project, title, status, number,
                    COALESCE(cnt_ui,0)+COALESCE(cnt_backend,0)+COALESCE(cnt_integration,0)+
                    COALESCE(cnt_infra,0)+COALESCE(cnt_ai_skill,0)+COALESCE(cnt_manual,0) AS activity,
                    TRIM(COALESCE(arch_ref,'')) AS arch_ref_norm
             FROM artifacts
             WHERE project IS NOT NULL
               AND type IN ({_tasks_placeholder_csv()})"""
    ).fetchall()

    for r in task_rows:
        pid = r["project"]
        color = colors.get(pid, {}).get("color", FALLBACK_COLOR)
        activity = int(r["activity"] or 0)
        # size: base 5, +1 per 3 activity points, cap at 20
        size = max(5, min(20, 5 + activity // 3))
        label_num = f"#{r['number']}" if r["number"] else ""
        nodes.append({
            "id": f"task:{r['id']}",
            "label": f"{label_num} {r['title'] or r['id']}".strip(),
            "type": r["type"],
            "project": pid,
            "color": color,
            "size": size,
            "level": 1,
            "meta": {"status": r["status"] or "open"},
        })
        # Parent edge (project → task) — used for force gravity, not rendered by default
        edges.append({
            "source": f"project:{pid}",
            "target": f"task:{r['id']}",
            "edge_type": "parent",
            "color": color,
        })

    # 3. arch_ref crosslinks — dedup via self-join a.id < b.id
    crosslinks = conn.execute(
        f"""SELECT a.id AS a_id, b.id AS b_id, a.arch_ref
             FROM artifacts a
             JOIN artifacts b
               ON TRIM(a.arch_ref) = TRIM(b.arch_ref)
              AND a.id < b.id
             WHERE a.arch_ref IS NOT NULL AND TRIM(a.arch_ref) != ''
               AND b.arch_ref IS NOT NULL AND TRIM(b.arch_ref) != ''
               AND a.type IN ({_tasks_placeholder_csv()})
               AND b.type IN ({_tasks_placeholder_csv()})
               AND a.project IS NOT NULL AND b.project IS NOT NULL"""
    ).fetchall()

    for cl in crosslinks:
        edges.append({
            "source": f"task:{cl['a_id']}",
            "target": f"task:{cl['b_id']}",
            "edge_type": "arch_ref",
            "color": "#F4A300",  # saffron for cross-links, always visible
        })

    return nodes, edges


def _query_level2(conn: sqlite3.Connection, colors: dict[str, dict[str, str]]) -> tuple[list[dict], list[dict]]:
    """
    Level 2 = Level 1 + all task_artifacts (~19710) with parent artifact→task edges.
    """
    nodes, edges = _query_level1(conn, colors)

    # Load tasks index for parent project color lookup
    task_project = {
        f"task:{r['id']}": r["project"]
        for r in conn.execute(
            f"SELECT id, project FROM artifacts WHERE project IS NOT NULL "
            f"AND type IN ({_tasks_placeholder_csv()})"
        )
    }

    art_rows = conn.execute(
        """SELECT id, task_id, artifact_type, file_name, round_num, created_at
             FROM task_artifacts
            WHERE task_id IS NOT NULL"""
    ).fetchall()

    for r in art_rows:
        parent_id = f"task:{r['task_id']}"
        pid = task_project.get(parent_id)
        if not pid:
            continue  # orphan artifact — parent task not found or not task-level
        color = colors.get(pid, {}).get("color", FALLBACK_COLOR)
        nodes.append({
            "id": f"artifact:{r['id']}",
            "label": r["file_name"] or f"artifact-{r['id']}",
            "type": r["artifact_type"] or "note",
            "project": pid,
            "color": color,
            "size": 2,
            "level": 2,
            "meta": {
                "task_id": r["task_id"],
                "round": r["round_num"],
                "created_at": r["created_at"],
            },
        })
        edges.append({
            "source": parent_id,
            "target": f"artifact:{r['id']}",
            "edge_type": "child",
            "color": color,
        })

    return nodes, edges


def galaxy_graph(routing_db: Path, projects_yml: Path, level: int = 1) -> dict[str, Any]:
    """
    Build graph payload for the /galaxy visualization.

    level=1: projects + tasks + arch_ref crosslinks (~1500 nodes)
    level=2: level 1 + all task_artifacts (~21000 nodes)
    """
    colors = _load_brand_colors(projects_yml)
    with _open(routing_db) as conn:
        if level == 2:
            nodes, edges = _query_level2(conn, colors)
        else:
            nodes, edges = _query_level1(conn, colors)

    return {
        "nodes": nodes,
        "edges": edges,
        "meta": {
            "level": level,
            "node_count": len(nodes),
            "edge_count": len(edges),
            "project_count": sum(1 for n in nodes if n["type"] == "project"),
            "projects": [
                {"id": pid, "name": m["name"], "color": m["color"]}
                for pid, m in colors.items()
            ],
        },
    }
