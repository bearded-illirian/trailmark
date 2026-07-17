"""
skills.py — Skills catalog proxy layer.

Fetches skill metadata from a configurable aihub-compatible endpoint,
augments each item with usage statistics computed from local
routing.db.task_artifacts (JOIN by artifact_type = skill.name).

Endpoint URL is provided by callers via `aihub_api_url` argument
(sourced from `config.paths.aihub_api_url`). If the URL is None or
empty, `fetch_aihub_skills()` returns an empty list — the Skills UI
degrades gracefully to an empty state, no network calls happen.

In-memory module-level cache with 60s TTL — designed for 1-worker
uvicorn. Cache serves stale-on-error when the endpoint is unreachable.
"""

from __future__ import annotations

import json
import sqlite3
import time
import urllib.error
import urllib.request
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional


FETCH_TIMEOUT = 5.0
CACHE_TTL = 60.0


# Module-level cache (per-worker). 1-worker systemd → single instance.
_CACHE: dict = {"data": None, "ts": 0.0}


@contextmanager
def _open_ro(db_path: Path) -> Iterator[sqlite3.Connection]:
    """Read-only connection to routing.db (PRAGMA query_only=1)."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA query_only = 1")
        yield conn
    finally:
        conn.close()


def fetch_aihub_skills(url: Optional[str]) -> list[dict]:
    """
    Fetch raw skill catalog from a configurable aihub-compatible endpoint.

    Null-safe: if `url` is None or empty, returns [] without touching cache
    or making any network call — the Skills tab degrades to an empty state.

    Cache: 60s TTL module-level dict. Returns cached data if fresh.
    On network / timeout error returns last cached data (stale-on-error);
    returns empty list if nothing was ever cached.
    """
    if not url:
        return []

    now = time.time()
    if _CACHE["data"] is not None and (now - _CACHE["ts"]) < CACHE_TTL:
        return _CACHE["data"]

    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT) as resp:
            body = resp.read().decode("utf-8")
        payload = json.loads(body)
        items = payload.get("items", [])
        _CACHE["data"] = items
        _CACHE["ts"] = now
        return items
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        # stale-on-error — return last cached data or empty
        return _CACHE["data"] or []


def _load_usage_map(db_path: Path) -> dict[str, dict]:
    """
    Build {skill_name: {total, d30, d7, last_used_at}} lookup — merged strategy.

    Two data sources (block 407 decision-07 combo):
    - skill_invocations (ground truth, forward-only) — 1 row = 1 skill invocation
    - skill_artifact_types (block 406, historical fallback) — mapping to artifact counts

    Priority: if skill has invocations > 0 → use invocation counts.
    Otherwise fallback to mapping counts (historical era before block 407).

    Returns dict keyed by skill_name. augment_with_usage() lookup by skill.name.
    """
    invocations_sql = (
        "SELECT skill_name, "
        "COUNT(*) AS total, "
        "SUM(CASE WHEN date(invoked_at) >= date('now', '-30 days') THEN 1 ELSE 0 END) AS d30, "
        "SUM(CASE WHEN date(invoked_at) >= date('now', '-7 days') THEN 1 ELSE 0 END) AS d7, "
        "MAX(invoked_at) AS last_used_at "
        "FROM skill_invocations "
        "GROUP BY skill_name"
    )
    mapping_sql = (
        "SELECT sat.skill_name, "
        "SUM(sat.weight) AS total, "
        "SUM(CASE WHEN date(ta.created_at) >= date('now', '-30 days') THEN sat.weight ELSE 0 END) AS d30, "
        "SUM(CASE WHEN date(ta.created_at) >= date('now', '-7 days') THEN sat.weight ELSE 0 END) AS d7, "
        "MAX(ta.created_at) AS last_used_at "
        "FROM task_artifacts ta "
        "INNER JOIN skill_artifact_types sat ON sat.artifact_type = ta.artifact_type "
        "WHERE ta.artifact_type IS NOT NULL "
        "GROUP BY sat.skill_name"
    )

    invocations: dict[str, dict] = {}
    mapping: dict[str, dict] = {}

    with _open_ro(db_path) as conn:
        try:
            for row in conn.execute(invocations_sql).fetchall():
                invocations[row["skill_name"]] = {
                    "usage_total": int(row["total"] or 0),
                    "usage_30d": int(row["d30"] or 0),
                    "usage_7d": int(row["d7"] or 0),
                    "last_used_at": row["last_used_at"],
                }
        except sqlite3.OperationalError:
            # skill_invocations table missing — skip (works on fresh DBs)
            pass

        try:
            for row in conn.execute(mapping_sql).fetchall():
                mapping[row["skill_name"]] = {
                    "usage_total": int(round(row["total"] or 0)),
                    "usage_30d": int(round(row["d30"] or 0)),
                    "usage_7d": int(round(row["d7"] or 0)),
                    "last_used_at": row["last_used_at"],
                }
        except sqlite3.OperationalError:
            # task_artifacts / skill_artifact_types missing (fresh DB) — skip
            pass

    # Merge: MAX per metric between invocation and mapping.
    # Transition period: mapping counts dominate (historical). Over time as
    # skill_invocations grows, invocation ground truth naturally overtakes
    # for actively-used skills. Both are valid estimates — take the higher.
    result: dict[str, dict] = {}
    all_names = set(invocations.keys()) | set(mapping.keys())
    zero = {"usage_total": 0, "usage_30d": 0, "usage_7d": 0, "last_used_at": None}
    for name in all_names:
        inv = invocations.get(name, zero)
        mp = mapping.get(name, zero)
        # last_used_at: take the more recent (string ISO 8601 compares correctly)
        last_used = None
        if inv["last_used_at"] and mp["last_used_at"]:
            last_used = max(inv["last_used_at"], mp["last_used_at"])
        else:
            last_used = inv["last_used_at"] or mp["last_used_at"]
        result[name] = {
            "usage_total": max(inv["usage_total"], mp["usage_total"]),
            "usage_30d": max(inv["usage_30d"], mp["usage_30d"]),
            "usage_7d": max(inv["usage_7d"], mp["usage_7d"]),
            "last_used_at": last_used,
        }
    return result


def augment_with_usage(items: list[dict], db_path: Path) -> list[dict]:
    """Merge usage stats into skill items by matching name == artifact_type."""
    usage = _load_usage_map(db_path)
    zero = {"usage_total": 0, "usage_30d": 0, "usage_7d": 0, "last_used_at": None}
    augmented: list[dict] = []
    for item in items:
        stats = usage.get(item.get("name"), zero)
        augmented.append({**item, **stats})
    return augmented


def get_all(db_path: Path, aihub_api_url: Optional[str] = None) -> dict:
    """Full catalog with augmented usage. Ready for AgentAugmentedListOut."""
    items = fetch_aihub_skills(aihub_api_url)
    augmented = augment_with_usage(items, db_path)
    return {"items": augmented, "total": len(augmented), "cached_at": _CACHE["ts"]}


def get_one(name: str, db_path: Path, aihub_api_url: Optional[str] = None) -> Optional[dict]:
    """Single skill by name with augmented usage. None if not found."""
    items = fetch_aihub_skills(aihub_api_url)
    for item in items:
        if item.get("name") == name:
            return augment_with_usage([item], db_path)[0]
    return None


# ── Block 403 — examples + aggregate stats ─────────────────────────────

def list_examples(name: str, db_path: Path, limit: int = 5) -> dict:
    """
    Recent artifacts of a given skill. LEFT JOIN with artifacts to fetch task
    title; task_title falls back to artifact id, then to raw task_id string.
    """
    sql = (
        "SELECT ta.file_name, ta.file_path, ta.task_id, ta.block_num, "
        "ta.round_num, ta.created_at, "
        "COALESCE(a.title, a.id, ta.task_id) AS task_title "
        "FROM task_artifacts ta LEFT JOIN artifacts a ON a.id = ta.task_id "
        "WHERE ta.artifact_type = ? "
        "ORDER BY ta.created_at DESC LIMIT ?"
    )
    with _open_ro(db_path) as conn:
        rows = conn.execute(sql, (name, limit)).fetchall()
    items = [
        {
            "file_name": r["file_name"],
            "file_path": r["file_path"],
            "task_id": r["task_id"],
            "task_title": r["task_title"],
            "block_num": r["block_num"],
            "round_num": r["round_num"],
            "created_at": r["created_at"],
        }
        for r in rows
    ]
    return {"name": name, "items": items}


def stats_skills(db_path: Path, aihub_api_url: Optional[str] = None) -> dict:
    """
    Aggregate methodology metrics for analytics tiles.

    Uses _load_usage_map() merged strategy (invocation log ground truth +
    mapping fallback) for consistency with /api/skills endpoint numbers.

    Returns:
        total_registered: len(catalog)
        used_30d: count of catalog skills where usage_30d > 0
        unused_90d: count of catalog skills where last_used_at older than 90d or None
        top_used_30d: [{name, count, display_name?}] ×10, sorted by usage_30d desc
        domain_coverage: [{domain, used, total}] grouped by category_slug
    """
    from collections import defaultdict

    catalog = fetch_aihub_skills(aihub_api_url)
    usage_map = _load_usage_map(db_path)

    # cutoff for "unused_90d" check
    with _open_ro(db_path) as conn:
        cutoff_90d = conn.execute("SELECT date('now', '-90 days')").fetchone()[0]

    used_30d = set()
    unused_90d = set()

    for item in catalog:
        name = item["name"]
        stats = usage_map.get(name)
        if stats and stats.get("usage_30d", 0) > 0:
            used_30d.add(name)
        last = stats.get("last_used_at") if stats else None
        if last is None or last[:10] < cutoff_90d:
            unused_90d.add(name)

    # top_used_30d — sort catalog by usage_30d desc, take top 10 with count > 0
    ranked = []
    for item in catalog:
        name = item["name"]
        stats = usage_map.get(name)
        cnt = stats.get("usage_30d", 0) if stats else 0
        if cnt > 0:
            ranked.append({
                "name": name,
                "count": cnt,
                "display_name": item.get("display_name"),
            })
    ranked.sort(key=lambda r: r["count"], reverse=True)
    top_used_30d = ranked[:10]

    # domain_coverage — group catalog by category_slug, count used
    coverage_buckets: dict[str, dict] = defaultdict(lambda: {"total": 0, "used": 0})
    for item in catalog:
        domain = item.get("category_slug") or "uncategorized"
        coverage_buckets[domain]["total"] += 1
        if item["name"] in used_30d:
            coverage_buckets[domain]["used"] += 1

    domain_coverage = [
        {"domain": d, "used": v["used"], "total": v["total"]}
        for d, v in sorted(coverage_buckets.items())
    ]

    return {
        "total_registered": len(catalog),
        "used_30d": len(used_30d),
        "unused_90d": len(unused_90d),
        "top_used_30d": top_used_30d,
        "domain_coverage": domain_coverage,
    }
