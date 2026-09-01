"""
schemas.py — Pydantic response models mirroring Block 2 dataclasses.

Kept separate so main.py stays focused on routing.
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel


class ProjectOut(BaseModel):
    id: str
    name: str
    path: str
    domain: Optional[str] = None
    status: str
    vds_visible: bool
    extras: dict[str, Any] = {}


class TaskOut(BaseModel):
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


class BlockOut(BaseModel):
    block_num: int
    title: Optional[str]
    status: str
    source: Optional[str]
    commit_hash: Optional[str]
    atom_type: Optional[str]
    parent_block_num: Optional[int]
    type: str
    sort_order: Optional[int]


class ArtifactOut(BaseModel):
    block_num_raw: str
    block_num_int: Optional[int]
    round_num: Optional[int]
    artifact_type: Optional[str]
    file_name: Optional[str]
    file_path: Optional[str]
    created_by: Optional[str]
    created_at: Optional[str]


class FSEntryOut(BaseModel):
    name: str
    type: str
    size: int
    is_text: bool


class FileContentOut(BaseModel):
    path: str
    content: str
    size: int


class StatsOut(BaseModel):
    today_count: int
    streak_days: int
    week_views: int


class AccessIn(BaseModel):
    project: Optional[str] = None
    target_type: str
    target_id: str


# ── Stats page ──────────────────────────────────────────────────────────

class HeatmapCell(BaseModel):
    date: str
    count: int


class Bar(BaseModel):
    label: str
    value: int


class BlockTimelineItem(BaseModel):
    block_num: Optional[int]
    title: Optional[str]
    status: str
    closed_at: Optional[str]
    commit_hash: Optional[str]


class Velocity(BaseModel):
    created: list[Bar] = []
    closed: list[Bar] = []


class StatsGlobalOut(BaseModel):
    scope: str = "global"
    top_numbers: dict[str, int]
    deploys: dict[str, int] = {}
    heatmap: list[HeatmapCell]
    top_projects: list[Bar]
    types_tasks: list[Bar]
    types_artifacts: list[Bar]
    top_accessed: list[Bar]
    velocity: Velocity
    recent: list[dict]


class StatsProjectOut(BaseModel):
    scope: str = "project"
    project_id: str
    top_numbers: dict[str, int]
    deploys: dict[str, int] = {}
    heatmap: list[HeatmapCell]
    types_tasks: list[Bar]
    types_artifacts: list[Bar]
    top_accessed: list[Bar]
    velocity: Velocity
    recent: list[dict]


class DeployOut(BaseModel):
    id: int
    project: str
    commit_sha: str
    deployed_at: str
    status: str
    ref_name: Optional[str] = None
    commit_msg: Optional[str] = None
    task_id: Optional[str] = None
    # display-only string — task_blocks stores mixed types (int, float, 'Y1.1', etc)
    block_num: Optional[str] = None
    raw_log: Optional[str] = None
    task_title: Optional[str] = None


class TaskDeploysGroupOut(BaseModel):
    id: str
    title: str
    number: Optional[int] = None
    status: Optional[str] = None
    count: int
    deploys: list[DeployOut]


class DeploysGroupedOut(BaseModel):
    tasks: list[TaskDeploysGroupOut] = []
    unlinked: list[DeployOut] = []


class StatsTaskOut(BaseModel):
    scope: str = "task"
    task: dict
    top_numbers: dict[str, int]
    blocks_timeline: list[BlockTimelineItem]
    artifacts_by_type: list[Bar]
    commits: list[str]


# ── Skills catalog (task vschk-platform--514 block 402) ────────────────────
# Proxy to aihub /api/skills/flow + augmented usage counts from
# routing.db.task_artifacts. works_with accepts list[str] or list[dict] —
# aihub returns mixed types (Block 401 hotfix).

class AgentAugmentedOut(BaseModel):
    name: str
    type: str
    display_name: Optional[str] = None
    pitch: Optional[str] = None
    description_ru: Optional[str] = None
    works_with: Optional[list] = None
    version: str = "1.0.0"
    category_slug: Optional[str] = None
    pack_slug: Optional[str] = None
    usage_total: int = 0
    usage_30d: int = 0
    usage_7d: int = 0
    last_used_at: Optional[str] = None


class AgentAugmentedListOut(BaseModel):
    items: list[AgentAugmentedOut]
    total: int
    cached_at: float = 0.0


# ── Block 403 — examples + skills stats ────────────────────────────────

class SkillExampleItem(BaseModel):
    file_name: Optional[str] = None
    file_path: Optional[str] = None
    task_id: Optional[str] = None
    task_title: Optional[str] = None
    block_num: Optional[str] = None
    round_num: Optional[int] = None
    created_at: Optional[str] = None


class SkillExamplesOut(BaseModel):
    name: str
    items: list[SkillExampleItem]


class TopUsedItem(BaseModel):
    name: str
    count: int
    display_name: Optional[str] = None


class DomainCoverage(BaseModel):
    domain: str
    used: int
    total: int


class SkillsStatsOut(BaseModel):
    total_registered: int
    used_30d: int
    unused_90d: int
    top_used_30d: list[TopUsedItem]
    domain_coverage: list[DomainCoverage]


# ── Galaxy graph (task vschk-flow-ui--649 block 1) ─────────────────────

class GalaxyNodeOut(BaseModel):
    id: str
    label: str
    type: str
    project: Optional[str] = None
    color: str
    size: int
    level: int
    meta: dict[str, Any] = {}


class GalaxyEdgeOut(BaseModel):
    source: str
    target: str
    edge_type: str
    color: str


class GalaxyProjectOut(BaseModel):
    id: str
    name: str
    color: str


class GalaxyMetaOut(BaseModel):
    level: int
    node_count: int
    edge_count: int
    project_count: int
    projects: list[GalaxyProjectOut] = []


class GalaxyGraphOut(BaseModel):
    nodes: list[GalaxyNodeOut]
    edges: list[GalaxyEdgeOut]
    meta: GalaxyMetaOut
