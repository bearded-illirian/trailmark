"""
stats.py — Read-only aggregations over routing.db + access.db for the Stats page.

Three scopes:
  global_stats()             — cross-project overview
  project_stats(project_id)  — same shape filtered by project
  task_stats(task_id)        — task-specific: blocks + artifacts + commits
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional


TASK_TYPES = ("task", "fast-track", "brief", "tz", "epic")


@contextmanager
def _open(db_path: Path) -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA query_only = 1")
        yield conn
    finally:
        conn.close()


def _access_metrics(access_db: Path) -> dict:
    """Fetch access-log derived metrics with graceful fallback if DB missing."""
    empty = {"today_count": 0, "week_calendar": 0, "week_views": 0, "streak_days": 0, "top_accessed": []}
    if not access_db.exists():
        return empty
    try:
        with sqlite3.connect(str(access_db)) as c:
            c.row_factory = sqlite3.Row
            today = c.execute(
                "SELECT COUNT(*) FROM access_log WHERE date(ts)=date('now')"
            ).fetchone()[0]
            week_cal = c.execute(
                "SELECT COUNT(*) FROM access_log "
                "WHERE date(ts) >= date('now', '-' || ((strftime('%w','now')+6)%7) || ' days')"
            ).fetchone()[0]
            week = c.execute(
                "SELECT COUNT(*) FROM access_log WHERE ts > datetime('now','-7 days')"
            ).fetchone()[0]
            days = [
                r[0] for r in c.execute(
                    "SELECT DISTINCT date(ts) FROM access_log ORDER BY 1 DESC LIMIT 60"
                ).fetchall()
            ]
            from datetime import date, timedelta
            cursor = date.today()
            streak = 0
            for d in days:
                if d == cursor.isoformat():
                    streak += 1
                    cursor -= timedelta(days=1)
                else:
                    break
            top = [
                {"label": r[0] or "?", "value": r[1]}
                for r in c.execute(
                    "SELECT target_id, COUNT(*) FROM access_log "
                    "WHERE ts > datetime('now','-30 days') "
                    "GROUP BY target_id ORDER BY 2 DESC LIMIT 10"
                ).fetchall()
            ]
        return {"today_count": today, "week_calendar": week_cal, "week_views": week, "streak_days": streak, "top_accessed": top}
    except sqlite3.Error:
        return empty


def _heatmap(conn: sqlite3.Connection, project_id: Optional[str] = None) -> list[dict]:
    where = "WHERE created_at >= date('now', '-365 days')"
    params: list = []
    if project_id:
        where += " AND task_id IN (SELECT id FROM artifacts WHERE project = ?)"
        params.append(project_id)
    rows = conn.execute(
        f"SELECT date(created_at) AS d, COUNT(*) AS c FROM task_artifacts {where} "
        f"GROUP BY d ORDER BY d",
        params,
    ).fetchall()
    return [{"date": r["d"], "count": r["c"]} for r in rows]


def _velocity(conn: sqlite3.Connection, project_id: Optional[str] = None) -> dict:
    """Last 12 weeks: created vs closed tasks."""
    where_p = "WHERE project = ?" if project_id else ""
    params = [project_id] if project_id else []
    created = conn.execute(
        f"SELECT strftime('%Y-%W', created_at) AS w, COUNT(*) FROM artifacts "
        f"{where_p} {'AND' if project_id else 'WHERE'} type IN {TASK_TYPES!r} "
        f"AND created_at >= date('now','-84 days') GROUP BY w ORDER BY w",
        params,
    ).fetchall()
    closed = conn.execute(
        f"SELECT strftime('%Y-%W', closed_at) AS w, COUNT(*) FROM artifacts "
        f"{where_p} {'AND' if project_id else 'WHERE'} type IN {TASK_TYPES!r} "
        f"AND closed_at IS NOT NULL AND closed_at >= date('now','-84 days') GROUP BY w ORDER BY w",
        params,
    ).fetchall()
    return {
        "created": [{"label": r[0], "value": r[1]} for r in created],
        "closed": [{"label": r[0], "value": r[1]} for r in closed],
    }


def _recent_tasks(conn: sqlite3.Connection, project_id: Optional[str] = None, limit: int = 10) -> list[dict]:
    where_p = "AND project = ?" if project_id else ""
    params: list = []
    if project_id:
        params.append(project_id)
    params.append(limit)
    rows = conn.execute(
        f"SELECT id, number, title, project, status, created_at FROM artifacts "
        f"WHERE type IN {TASK_TYPES!r} {where_p} "
        f"ORDER BY created_at DESC LIMIT ?",
        params,
    ).fetchall()
    return [dict(r) for r in rows]


def _activity_week_metrics(conn: sqlite3.Connection, project_id: Optional[str] = None) -> dict:
    """Real activity: artifacts created today, this calendar week (Mon-Sun), last 7 days.

    Sourced from task_artifacts.created_at (not access_log visits) so a fresh
    instance still shows accumulated project activity.
    """
    where_p = ""
    params: list = []
    if project_id:
        where_p = " AND task_id IN (SELECT id FROM artifacts WHERE project = ?)"
        params.append(project_id)
    today_count = conn.execute(
        "SELECT COUNT(*) FROM task_artifacts "
        "WHERE date(created_at, 'localtime') = date('now', 'localtime')" + where_p,
        params,
    ).fetchone()[0]
    week_calendar = conn.execute(
        "SELECT COUNT(*) FROM task_artifacts "
        "WHERE date(created_at, 'localtime') >= "
        "date('now', 'localtime', '-' || ((strftime('%w','now','localtime')+6)%7) || ' days')"
        + where_p,
        params,
    ).fetchone()[0]
    week_views = conn.execute(
        "SELECT COUNT(*) FROM task_artifacts "
        "WHERE date(created_at, 'localtime') >= date('now', 'localtime', '-7 days')"
        + where_p,
        params,
    ).fetchone()[0]
    return {"today_count": today_count, "week_calendar": week_calendar, "week_views": week_views}


def _task_counts(conn: sqlite3.Connection, project_id: Optional[str] = None) -> dict:
    where_p = "AND project = ?" if project_id else ""
    p = [project_id] if project_id else []
    total = conn.execute(
        f"SELECT COUNT(*) FROM artifacts WHERE type IN {TASK_TYPES!r} {where_p}", p
    ).fetchone()[0]
    open_ = conn.execute(
        f"SELECT COUNT(*) FROM artifacts WHERE type IN {TASK_TYPES!r} AND status='open' {where_p}", p
    ).fetchone()[0]
    artifacts = conn.execute(
        "SELECT COUNT(*) FROM task_artifacts"
        + (
            " WHERE task_id IN (SELECT id FROM artifacts WHERE project = ?)"
            if project_id else ""
        ),
        p,
    ).fetchone()[0]
    return {"tasks_total": total, "tasks_open": open_, "tasks_closed": total - open_, "artifacts_total": artifacts}


def _deploy_metrics(conn: sqlite3.Connection, project_id: Optional[str] = None) -> dict:
    """Deploy activity counters: total (ok status), today, this calendar week (Mon-Sun),
    last 7 days. Uses 'localtime' modifier on deployed_at (UTC storage → local day boundary).

    Empty {} if deploys table is not present (fresh instance without Block 301).
    """
    has_tbl = conn.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='deploys'"
    ).fetchone()[0]
    if not has_tbl:
        return {}
    where_p = " AND project = ?" if project_id else ""
    params: list = [project_id] if project_id else []
    total = conn.execute(
        f"SELECT COUNT(*) FROM deploys WHERE status='ok'{where_p}", params
    ).fetchone()[0]
    today = conn.execute(
        "SELECT COUNT(*) FROM deploys "
        "WHERE date(deployed_at, 'localtime') = date('now', 'localtime')" + where_p,
        params,
    ).fetchone()[0]
    week_calendar = conn.execute(
        "SELECT COUNT(*) FROM deploys "
        "WHERE date(deployed_at, 'localtime') >= "
        "date('now', 'localtime', '-' || ((strftime('%w','now','localtime')+6)%7) || ' days')"
        + where_p,
        params,
    ).fetchone()[0]
    week_views = conn.execute(
        "SELECT COUNT(*) FROM deploys "
        "WHERE date(deployed_at, 'localtime') >= date('now', 'localtime', '-7 days')" + where_p,
        params,
    ).fetchone()[0]
    return {
        "deploys_total": total,
        "deploys_today": today,
        "deploys_week_calendar": week_calendar,
        "deploys_week_views": week_views,
    }


def global_stats(db_path: Path, access_db: Path) -> dict:
    access = _access_metrics(access_db)
    with _open(db_path) as conn:
        counts = _task_counts(conn)
        activity = _activity_week_metrics(conn)
        heatmap = _heatmap(conn)
        top_projects = [
            {"label": r[0] or "?", "value": r[1]}
            for r in conn.execute(
                "SELECT project, COUNT(*) FROM artifacts "
                f"WHERE type IN {TASK_TYPES!r} AND created_at >= date('now','-30 days') "
                "GROUP BY project ORDER BY 2 DESC LIMIT 10"
            ).fetchall()
        ]
        types_tasks = [
            {"label": r[0], "value": r[1]}
            for r in conn.execute(
                f"SELECT type, COUNT(*) FROM artifacts WHERE type IN {TASK_TYPES!r} "
                "GROUP BY type ORDER BY 2 DESC"
            ).fetchall()
        ]
        types_artifacts = [
            {"label": r[0], "value": r[1]}
            for r in conn.execute(
                "SELECT artifact_type, COUNT(*) FROM task_artifacts "
                "GROUP BY artifact_type ORDER BY 2 DESC LIMIT 10"
            ).fetchall()
        ]
        velocity = _velocity(conn)
        recent = _recent_tasks(conn)
        deploys = _deploy_metrics(conn)
    return {
        "scope": "global",
        "top_numbers": {
            **counts,
            "streak_days": access["streak_days"],
            "today_count": activity["today_count"],
            "week_calendar": activity["week_calendar"],
            "week_views": activity["week_views"],
        },
        "deploys": deploys,
        "heatmap": heatmap,
        "top_projects": top_projects,
        "types_tasks": types_tasks,
        "types_artifacts": types_artifacts,
        "top_accessed": access["top_accessed"],
        "velocity": velocity,
        "recent": recent,
    }


def project_stats(db_path: Path, access_db: Path, project_id: str) -> dict:
    access = _access_metrics(access_db)
    with _open(db_path) as conn:
        counts = _task_counts(conn, project_id)
        activity = _activity_week_metrics(conn, project_id)
        heatmap = _heatmap(conn, project_id)
        types_tasks = [
            {"label": r[0], "value": r[1]}
            for r in conn.execute(
                f"SELECT type, COUNT(*) FROM artifacts WHERE type IN {TASK_TYPES!r} "
                "AND project = ? GROUP BY type ORDER BY 2 DESC",
                (project_id,),
            ).fetchall()
        ]
        types_artifacts = [
            {"label": r[0], "value": r[1]}
            for r in conn.execute(
                "SELECT artifact_type, COUNT(*) FROM task_artifacts "
                "WHERE task_id IN (SELECT id FROM artifacts WHERE project = ?) "
                "GROUP BY artifact_type ORDER BY 2 DESC LIMIT 10",
                (project_id,),
            ).fetchall()
        ]
        velocity = _velocity(conn, project_id)
        recent = _recent_tasks(conn, project_id)
        deploys = _deploy_metrics(conn, project_id)
    return {
        "scope": "project",
        "project_id": project_id,
        "top_numbers": {
            **counts,
            "today_count": activity["today_count"],
            "week_calendar": activity["week_calendar"],
            "week_views": activity["week_views"],
        },
        "deploys": deploys,
        "heatmap": heatmap,
        "types_tasks": types_tasks,
        "types_artifacts": types_artifacts,
        "top_accessed": access["top_accessed"],
        "velocity": velocity,
        "recent": recent,
    }


def task_stats(db_path: Path, task_id: str) -> Optional[dict]:
    with _open(db_path) as conn:
        task = conn.execute(
            "SELECT id, number, title, project, status, created_at, closed_at "
            "FROM artifacts WHERE id = ?",
            (task_id,),
        ).fetchone()
        if task is None:
            return None
        blocks = [
            dict(r) for r in conn.execute(
                "SELECT block_num, title, status, closed_at, commit_hash "
                "FROM task_blocks WHERE task_id = ? "
                "ORDER BY COALESCE(sort_order, block_num * 100), block_num",
                (task_id,),
            ).fetchall()
        ]
        artifacts_by_type = [
            {"label": r[0], "value": r[1]}
            for r in conn.execute(
                "SELECT artifact_type, COUNT(*) FROM task_artifacts WHERE task_id = ? "
                "GROUP BY artifact_type ORDER BY 2 DESC",
                (task_id,),
            ).fetchall()
        ]
        artifacts_total = sum(a["value"] for a in artifacts_by_type)
    done = sum(1 for b in blocks if b["status"] == "done")
    pending = sum(1 for b in blocks if b["status"] in ("pending", "open"))
    commits = [b["commit_hash"] for b in blocks if b.get("commit_hash")]
    return {
        "scope": "task",
        "task": dict(task),
        "top_numbers": {
            "blocks_total": len(blocks),
            "blocks_done": done,
            "blocks_pending": pending,
            "artifacts_total": artifacts_total,
            "commits_total": len(commits),
        },
        "blocks_timeline": blocks,
        "artifacts_by_type": artifacts_by_type,
        "commits": commits,
    }
