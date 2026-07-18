"""
main.py — Flow Web UI FastAPI application.

Read-only browser over routing.db + task_artifacts + projects.yml + project fs.
Only write endpoint: POST /api/access (habit tracking).

Endpoints:
  GET  /                          → JSON banner (HTML shell added in Block 4)
  GET  /health
  GET  /api/projects
  GET  /api/projects/{id}
  GET  /api/projects/{id}/tree?path=
  GET  /api/projects/{id}/file?path=
  GET  /api/projects/{id}/tasks
  GET  /api/tasks/{task_id}
  GET  /api/tasks/{task_id}/blocks
  GET  /api/tasks/{task_id}/artifacts
  GET  /api/artifacts/read?path=
  GET  /api/stats
  POST /api/access
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import access, db, fs, projects, skills, stats
from .config import load_config
from .schemas import (
    AccessIn,
    AgentAugmentedListOut,
    AgentAugmentedOut,
    ArtifactOut,
    BlockOut,
    DeployOut,
    DeploysGroupedOut,
    FSEntryOut,
    FileContentOut,
    ProjectOut,
    SkillExamplesOut,
    SkillsStatsOut,
    StatsGlobalOut,
    StatsOut,
    StatsProjectOut,
    StatsTaskOut,
    TaskDeploysGroupOut,
    TaskOut,
)


# ── Bootstrap ────────────────────────────────────────────────────────────

_ROOT = Path(__file__).resolve().parent.parent
_CONFIG_PATH = _ROOT / "config.yml"
if not _CONFIG_PATH.exists():
    _CONFIG_PATH = _ROOT / "config.example.yml"

CFG = load_config(_CONFIG_PATH)
# Workspace root is derived: routing_db lives at <workspace>/tasks/routing.db,
# so parent.parent gives us the workspace root regardless of layout.
_WORKSPACE_ROOT = CFG.paths.routing_db.parent.parent

app = FastAPI(
    title="flow-ui",
    version="0.1.0",
    docs_url="/docs",
    redoc_url=None,
    openapi_url="/openapi.json",
)

if os.getenv("AUTH_MODE") == "platform" and CFG.paths.platform_db:
    # Reference SSO middleware — see AUTH.md. Optional module (may be absent
    # in public/framework distributions). Import guarded so distributions
    # without app/auth.py still boot cleanly when AUTH_MODE is unset.
    from . import auth  # type: ignore[import-not-found]
    app.add_middleware(auth.AuthMiddleware, platform_db=CFG.paths.platform_db)

_STATIC_DIR = _ROOT / "app" / "static"
_TEMPLATES_DIR = _ROOT / "app" / "templates"
if _STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))


# ── Root + health ────────────────────────────────────────────────────────

def _detect_demo_active() -> bool:
    """Return True if any demo row exists in DB (guides banner display).
    Graceful: on pre-migration DB (no is_demo column) returns False silently.
    """
    try:
        with db._connect(CFG.paths.routing_db) as conn:  # noqa: SLF001
            row = conn.execute("SELECT COUNT(*) FROM artifacts WHERE is_demo = 1").fetchone()
            return bool(row and row[0] > 0)
    except Exception:
        return False


@app.get("/")
def root(request: Request):
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "stats": access.get_stats(CFG.paths.access_log),
            "is_demo_active": _detect_demo_active(),
        },
    )


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


# ── Projects ────────────────────────────────────────────────────────────

def _load_registry() -> list[projects.Project]:
    reg = projects.parse_projects(CFG.paths.projects_yml)
    return projects.active_only(reg.projects)


def _get_project_or_404(pid: str) -> projects.Project:
    for p in _load_registry():
        if p.id == pid:
            return p
    raise HTTPException(status_code=404, detail=f"project not found: {pid}")


@app.get("/api/projects", response_model=list[ProjectOut])
def list_projects() -> list[ProjectOut]:
    return [
        ProjectOut(
            id=p.id, name=p.name, path=str(p.path), domain=p.domain,
            status=p.status, vds_visible=p.vds_visible, extras=p.extras,
        )
        for p in _load_registry()
    ]


@app.get("/api/projects/{project_id}", response_model=ProjectOut)
def get_project(project_id: str) -> ProjectOut:
    p = _get_project_or_404(project_id)
    return ProjectOut(
        id=p.id, name=p.name, path=str(p.path), domain=p.domain,
        status=p.status, vds_visible=p.vds_visible, extras=p.extras,
    )


def _effective_path(p: projects.Project) -> Path:
    """Return VDS deploy dir when CFG.mode='vds', else local project path."""
    if CFG.mode == "vds" and p.deploy_dir_vds:
        return p.deploy_dir_vds
    return p.path


@app.get("/api/projects/{project_id}/tree", response_model=list[FSEntryOut])
def project_tree(project_id: str, path: str = Query("")) -> list[FSEntryOut]:
    p = _get_project_or_404(project_id)
    try:
        entries = fs.walk_dir(_effective_path(p), path, CFG.filesystem.ignore, CFG.filesystem.text_extensions)
    except (ValueError, NotADirectoryError, FileNotFoundError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    return [FSEntryOut(name=e.name, type=e.type, size=e.size, is_text=e.is_text) for e in entries]


@app.get("/api/projects/{project_id}/file", response_model=FileContentOut)
def project_file(project_id: str, path: str = Query(...)) -> FileContentOut:
    p = _get_project_or_404(project_id)
    try:
        content = fs.read_text_file(
            _effective_path(p), path, CFG.filesystem.max_file_size_kb, CFG.filesystem.text_extensions
        )
    except (ValueError, FileNotFoundError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    return FileContentOut(path=path, content=content, size=len(content))


@app.get("/api/projects/{project_id}/tasks", response_model=list[TaskOut])
def project_tasks(project_id: str, limit: int = Query(200, ge=1, le=1000)) -> list[TaskOut]:
    _get_project_or_404(project_id)
    tasks = db.list_tasks(CFG.paths.routing_db, project_id=project_id, limit=limit)
    return [TaskOut(**t.__dict__) for t in tasks]


@app.get("/api/projects/{project_id}/deploys", response_model=DeploysGroupedOut)
def project_deploys(project_id: str) -> DeploysGroupedOut:
    _get_project_or_404(project_id)
    data = db.list_deploys_grouped_by_project(CFG.paths.routing_db, project_id)
    return DeploysGroupedOut(
        tasks=[
            TaskDeploysGroupOut(
                id=g["id"],
                title=g["title"],
                number=g.get("number"),
                status=g.get("status"),
                count=g["count"],
                deploys=[DeployOut(**d.__dict__) for d in g["deploys"]],
            )
            for g in data["tasks"]
        ],
        unlinked=[DeployOut(**d.__dict__) for d in data["unlinked"]],
    )


@app.get("/api/deploys/task/{task_id}", response_model=list[DeployOut])
def task_deploys(task_id: str) -> list[DeployOut]:
    return [DeployOut(**d.__dict__) for d in db.list_deploys_for_task(CFG.paths.routing_db, task_id)]


# ── Tasks ───────────────────────────────────────────────────────────────

@app.get("/api/tasks/{task_id}", response_model=TaskOut)
def get_task(task_id: str) -> TaskOut:
    t = db.get_task(CFG.paths.routing_db, task_id)
    if t is None:
        raise HTTPException(status_code=404, detail=f"task not found: {task_id}")
    return TaskOut(**t.__dict__)


@app.get("/api/tasks/{task_id}/blocks", response_model=list[BlockOut])
def task_blocks(task_id: str) -> list[BlockOut]:
    return [BlockOut(**b.__dict__) for b in db.list_blocks(CFG.paths.routing_db, task_id)]


@app.get("/api/tasks/{task_id}/artifacts", response_model=list[ArtifactOut])
def task_artifacts(task_id: str) -> list[ArtifactOut]:
    return [ArtifactOut(**a.__dict__) for a in db.list_artifacts(CFG.paths.routing_db, task_id)]


# ── Artifact read + Habit tracking ──────────────────────────────────────

@app.get("/api/artifacts/read", response_model=FileContentOut)
def artifact_read(path: str = Query(...)) -> FileContentOut:
    try:
        content = db.read_artifact_file(path, _WORKSPACE_ROOT, max_kb=CFG.filesystem.max_file_size_kb)
    except (ValueError, FileNotFoundError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    return FileContentOut(path=path, content=content, size=len(content))


@app.get("/api/stats", response_model=StatsOut)
def habit_stats() -> StatsOut:
    return StatsOut(**access.get_stats(CFG.paths.access_log))


@app.post("/api/access")
def record_access(item: AccessIn) -> dict:
    access.log_access(CFG.paths.access_log, item.project, item.target_type, item.target_id)
    return {"ok": True}


# ── Stats (3 scopes) ────────────────────────────────────────────────────

@app.get("/api/stats/global", response_model=StatsGlobalOut)
def stats_global() -> StatsGlobalOut:
    return StatsGlobalOut(**stats.global_stats(CFG.paths.routing_db, CFG.paths.access_log))


@app.get("/api/stats/project/{project_id}", response_model=StatsProjectOut)
def stats_project(project_id: str) -> StatsProjectOut:
    _get_project_or_404(project_id)
    return StatsProjectOut(**stats.project_stats(CFG.paths.routing_db, CFG.paths.access_log, project_id))


@app.get("/api/stats/task/{task_id}", response_model=StatsTaskOut)
def stats_task(task_id: str) -> StatsTaskOut:
    data = stats.task_stats(CFG.paths.routing_db, task_id)
    if data is None:
        raise HTTPException(status_code=404, detail=f"task not found: {task_id}")
    return StatsTaskOut(**data)


# ── Skills catalog (task vschk-platform--514 block 402) ─────────────────

@app.get("/api/skills", response_model=AgentAugmentedListOut)
def list_skills() -> AgentAugmentedListOut:
    data = skills.get_all(CFG.paths.routing_db, CFG.paths.aihub_api_url)
    return AgentAugmentedListOut(**data)


@app.get("/api/skills/{name}", response_model=AgentAugmentedOut)
def get_skill(name: str) -> AgentAugmentedOut:
    item = skills.get_one(name, CFG.paths.routing_db, CFG.paths.aihub_api_url)
    if item is None:
        raise HTTPException(status_code=404, detail=f"skill not found: {name}")
    return AgentAugmentedOut(**item)


@app.get("/api/skills/{name}/examples", response_model=SkillExamplesOut)
def skill_examples(name: str, limit: int = 5) -> SkillExamplesOut:
    if skills.get_one(name, CFG.paths.routing_db, CFG.paths.aihub_api_url) is None:
        raise HTTPException(status_code=404, detail=f"skill not found: {name}")
    return SkillExamplesOut(**skills.list_examples(name, CFG.paths.routing_db, limit=limit))


@app.get("/api/stats/skills", response_model=SkillsStatsOut)
def stats_skills_endpoint() -> SkillsStatsOut:
    return SkillsStatsOut(**skills.stats_skills(CFG.paths.routing_db, CFG.paths.aihub_api_url))
