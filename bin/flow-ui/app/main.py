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

import mimetypes
import os
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import access, db, fs, galaxy, projects, skills, stats
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
    GalaxyGraphOut,
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


def _asset(path: str) -> str:
    """Адрес статики с отпечатком файла в запросе.

    Портал у клиента живёт открытой вкладкой — мы сами это советуем в документе
    «Как мы работаем». Без отпечатка вкладка держит скрипт, загруженный когда-то,
    и выкаченная правка до клиента не доезжает, пока он не догадается перезагрузить
    страницу. 22.08 на этом потеряли ход: обложка была уже на проде, а в открытой
    вкладке по-прежнему открывался первый документ.

    Отпечаток — время правки файла. stat на каждый рендер страницы портала дешевле,
    чем вычисление при старте: процесс переживает выкладку, а файл нет.
    """
    rel = path.lstrip("/")
    try:
        stamp = format(int((_STATIC_DIR / rel).stat().st_mtime), "x")
    except OSError:
        return f"/static/{rel}"
    return f"/static/{rel}?v={stamp}"


templates.env.globals["asset"] = _asset


# ── Partner routes (task 624) ────────────────────────────────────────────
from . import partners_api  # noqa: E402
partners_api.register_routes(app, CFG)


# ── External shares routes (task 664) ────────────────────────────────────
from . import shares_api  # noqa: E402
shares_api.register_routes(app, CFG)


# ── Portal admin routes (task 666 Block 7001, Wave 7 W7) ────────────────
from . import portals_api  # noqa: E402
portals_api.register_routes(app, CFG)


# ── Task-engine kit routes (task 651 block 530) ─────────────────────────
from fastapi import HTTPException as _TE_HTTPExc  # noqa: E402
from pathlib import Path as _TE_Path  # noqa: E402
from . import partners as _te_partners  # noqa: E402
from .kits.task_engine.task_engine_router import create_router as _te_create_router  # noqa: E402


def _te_auth_fn(token: str) -> dict:
    if not CFG.paths.partners_db:
        raise _TE_HTTPExc(500, "partners_db not configured")
    p = _te_partners.get_partner_by_token(_TE_Path(CFG.paths.partners_db).expanduser(), token)
    if not p:
        raise _TE_HTTPExc(401, "Invalid token")
    return p


def _te_source_filter_fn(partner: dict) -> dict:
    # v1.1: убрали shared source — задачи ставятся на человека, а не на группу.
    # Всё персонально: single personal source (writable).
    # Shared оставлен в architecture kit'а для future federated scenarios.
    portal_type = partner.get("portal_type") or "partner"
    folder = partner.get("folder_path") or partner.get("code") or ""
    root = _TE_Path(CFG.paths.portals_root or CFG.paths.partner_content_root or "").expanduser()
    personal_dir = root / portal_type / folder
    # v1.4.1: kit-owned data isolated в hidden .kit-data/ подпапке
    # (auto-hidden от partners_api tree через startswith(".") skip)
    return {
        "personal": {
            "path": str(personal_dir / ".kit-data" / "tasks.sqlite"),
            "label": "Личные",
            "badgeColor": "var(--brand)",
            "writable": True,
        }
    }


def _te_participants_fn(partner: dict) -> list:
    """Кому можно назначить задачу на этом портале."""
    if not CFG.paths.partners_db:
        return []
    rows = _te_partners.list_participants(
        _TE_Path(CFG.paths.partners_db).expanduser(), int(partner["id"])
    )
    return [r["name"] for r in rows]


app.include_router(
    _te_create_router(
        auth_fn=_te_auth_fn,
        source_filter_fn=_te_source_filter_fn,
        participants_fn=_te_participants_fn,
    ),
    prefix="/api/tasks",
)


# ── Root + health ────────────────────────────────────────────────────────

@app.get("/")
def root(request: Request):
    return templates.TemplateResponse(
        request,
        "index.html",
        {"stats": access.get_stats(CFG.paths.access_log)},
    )


@app.get("/extranet/{token}/")
def partner_portal(request: Request, token: str):
    """Extranet portal — витрина для любых внешних адресатов по magic-link.

    Канонический адрес с task 695 block 20. Раньше маршрут назывался /partner/,
    но из 12 живых порталов 8 — клиенты, 2 ученика и лишь 2 партнёра: имя врало
    для двух третей адресатов. Старый адрес остаётся вечным редиректом (block 21) —
    11 ссылок уже на руках у людей.

    Витрина одна на все типы адресатов (решение Р-5): общий адрес и раздельные
    интерфейсы не сочетаются. Шаблон и обработчик не изменились — только имя пути.
    """
    return templates.TemplateResponse(
        request,
        "partner.html",
        {"token": token},
    )


@app.get("/partner/{token}/")
def partner_portal_legacy_redirect(request: Request, token: str):
    """Вечный редирект со старого адреса портала (task 695 block 21).

    Маршрут переименован в /extranet/ блоком 20, но 11 ссылок уже на руках у людей —
    в переписках, закладках, письмах. Этот редирект остаётся в коде навсегда: удалить
    его — значит обрушить те ссылки.

    Статус 302, а не 301, сознательно: 301 кешируется браузером бессрочно и не
    отзывается, а в этой задаче уже был один ошибочный выбор маршрута (коммит 3fc0fa6).
    Лишний запрос на визит дешевле, чем невозможность передумать. Аргумент про
    поисковую индексацию здесь не работает — порталы приватные.
    """
    target = f"/extranet/{token}/"
    if request.url.query:
        target = f"{target}?{request.url.query}"
    return RedirectResponse(url=target, status_code=302)


@app.get("/api/partner/{token}/{path:path}")
def partner_api_legacy_redirect(request: Request, token: str, path: str):
    """Редирект старого API — страховка от закешированного фронта (task 695 block 21).

    Страничного редиректа мало: статика отдаётся без Cache-Control (только etag), поэтому
    браузер с сохранённым partner.js прежней версии продолжит звать /api/partner/... даже
    на новой странице — до ревалидации. Портал отрисовал бы пустое дерево без единой ошибки.

    Catch-all покрывает все пять маршрутов (info / tree / file / asset / images-in-folder).
    Query string пробрасывается обязательно: /file вызывается как ?path=X, без него 422.
    """
    target = f"/api/extranet/{token}/{path}"
    if request.url.query:
        target = f"{target}?{request.url.query}"
    return RedirectResponse(url=target, status_code=302)


@app.get("/personal-flow/")
def personal_flow_view(request: Request):
    """Personal Flow — per-user private space (task radar-os--660 block 6003).

    SSO cookie auth (radar_session на .vschk.online scope, расшарен с
    team.radar.vschk.online). Session context (tenant_code + employee_id +
    mode_role) получается через cross-domain fetch к
    https://team.radar.vschk.online/radar/api/session/verify.php?mode=personal_flow
    (Block 6002 verify endpoint) на frontend side (see personal_flow.js).

    Sub-navigation через hash routing (#/settings / #/tab/X / #/file/Y /
    #/analytics) — client-side SPA style, backend видит только /personal-flow/.

    Empty views placeholders до Waves 6.4-6.9 fill real content:
    - Файлы: пустой tree (Wave 4 sync files через Соня)
    - Настройки: Google Picker + подключение Drive (Block 6004)
    - Аналитика: dashboard widgets (Wave 7)
    """
    return templates.TemplateResponse(
        request,
        "personal_flow.html",
        {},
    )


def _find_preview_image(share_folder: Path) -> Optional[str]:
    """Find preview image for OG cards.

    Priority:
      1. Explicit cover file (cover.png / cover.jpg / og-image.png) in root
      2. First image in root of share folder
      3. First image anywhere (recursive)
    Returns relative path or None.
    """
    if not share_folder.exists():
        return None
    exts = {".png", ".jpg", ".jpeg", ".webp"}
    # Priority 1: explicit cover
    for name in ("cover.png", "cover.jpg", "cover.jpeg", "cover.webp", "og-image.png", "og-image.jpg"):
        p = share_folder / name
        if p.exists() and p.is_file():
            return name
    # Priority 2: image at root
    for f in sorted(share_folder.iterdir()):
        if f.is_file() and f.suffix.lower() in exts and not f.name.startswith("."):
            return f.name
    # Priority 3: recursive fallback
    for f in sorted(share_folder.rglob("*")):
        if f.is_file() and f.suffix.lower() in exts and not f.name.startswith("."):
            return str(f.relative_to(share_folder))
    return None


@app.api_route("/share/{token}/", methods=["GET", "HEAD"])
def share_portal(request: Request, token: str):
    """Public external share portal (task 664). Accepts either magic-token OR human code as URL slug.
    Supports HEAD requests (social crawlers check reachability before GET).
    Logs visit + serves share.html shell."""
    from . import shares as _shares
    if not CFG.paths.external_shares_db:
        raise HTTPException(500, "external_shares_db not configured")
    share = _shares.get_share_by_token_or_code(
        Path(CFG.paths.external_shares_db).expanduser(), token
    )
    if not share:
        raise HTTPException(404, "Invalid or expired share link")
    # Log visit (silent — failures don't break page)
    try:
        ip = request.client.host if request.client else None
        xff = request.headers.get("x-forwarded-for")
        if xff:
            ip = xff.split(",")[0].strip()
        _shares.log_visit(
            Path(CFG.paths.external_shares_db).expanduser(),
            share_id=share["id"],
            ip_address=ip,
            user_agent=request.headers.get("user-agent"),
            referer=request.headers.get("referer"),
        )
    except Exception:
        pass  # log_visit failures should not break the page
    # Preserve whichever identifier user typed (token or code) — keeps URL pretty in browser
    # + means all OG references stay on same URL, which soc crawlers actually fetched
    ident = token
    # Resolve preview image для OG-тегов (first image in share folder)
    preview_image_url = None
    if CFG.paths.external_shares_root:
        folder = Path(CFG.paths.external_shares_root).expanduser() / share.get("folder_path", share["code"])
        img_rel = _find_preview_image(folder)
        if img_rel:
            preview_image_url = f"https://flow.vschk.online/api/shares/{ident}/asset?path={img_rel}"
    try:
        return templates.TemplateResponse(
            request,
            "share.html",
            {
                "token": ident,
                "title": share["title"],
                "description": share.get("description") or "",
                "preview_image": preview_image_url,
                "share_url": f"https://flow.vschk.online/share/{ident}/",
            },
        )
    except Exception:
        # Template pending block 1003 — return placeholder JSON for now
        return {
            "token": token,
            "title": share["title"],
            "description": share.get("description"),
            "note": "share.html template pending block 1003",
        }


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


# MIME whitelist for /asset endpoint — mirror partners_api._is_allowed_mime.
_ASSET_ALLOWED_PREFIXES = ("image/", "audio/", "video/")
_ASSET_ALLOWED_EXACT = {"application/pdf", "application/octet-stream"}

# Image extensions for /images-in-folder gallery endpoint (block 677-4).
# Mirror of IMAGE_EXTS in partner.js + app.js.
_IMAGE_EXTS = frozenset({"png", "jpg", "jpeg", "gif", "svg", "webp", "avif", "bmp", "ico"})


def _asset_mime_allowed(mime: str) -> bool:
    if not mime:
        return True
    if mime in _ASSET_ALLOWED_EXACT:
        return True
    return any(mime.startswith(p) for p in _ASSET_ALLOWED_PREFIXES)


@app.api_route("/api/projects/{project_id}/asset", methods=["GET", "HEAD"])
def project_asset(project_id: str, path: str = Query(..., description="Relative path to binary asset")):
    """Serve binary assets (PDF/PNG/MP3/MP4/etc) with correct Content-Type.

    Mirror of shares_api /asset pattern. Path traversal check inline: resolve
    against project root and reject if outside. No `filename=` in FileResponse
    → inline disposition, browsers render instead of downloading.
    """
    p = _get_project_or_404(project_id)
    base = Path(_effective_path(p)).resolve()

    # Path traversal guard — target must resolve inside project root.
    try:
        target = (base / path).resolve()
        target.relative_to(base)
    except (ValueError, RuntimeError):
        raise HTTPException(status_code=400, detail="Path escapes project root")

    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail=f"Asset not found: {path}")

    media_type, _ = mimetypes.guess_type(str(target))
    if not media_type:
        media_type = "application/octet-stream"

    if not _asset_mime_allowed(media_type):
        raise HTTPException(status_code=415, detail=f"MIME type not allowed: {media_type}")

    return FileResponse(path=str(target), media_type=media_type)


@app.get("/api/projects/{project_id}/images-in-folder", response_model=list[FSEntryOut])
def project_images_in_folder(
    project_id: str,
    path: str = Query("", description="Subpath under project root (empty = root)"),
) -> list[FSEntryOut]:
    """Return all image files in a specific folder (for lightbox gallery, block 677-5)."""
    p = _get_project_or_404(project_id)
    base = Path(_effective_path(p)).resolve()

    # Path traversal guard — target must resolve inside project root.
    try:
        target = (base / path).resolve()
        target.relative_to(base)
    except (ValueError, RuntimeError):
        raise HTTPException(status_code=400, detail="Path escapes project root")

    if not target.exists() or not target.is_dir():
        raise HTTPException(status_code=404, detail=f"Folder not found: {path}")

    images = []
    for child in sorted(target.iterdir()):
        if not child.is_file() or child.name.startswith("."):
            continue
        ext = child.suffix.lower().lstrip(".")
        if ext not in _IMAGE_EXTS:
            continue
        images.append(FSEntryOut(
            name=child.name,
            type="file",
            size=child.stat().st_size,
            is_text=False,
        ))
    return images


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


@app.api_route("/api/artifacts/asset", methods=["GET", "HEAD"])
def artifact_asset(path: str = Query(..., description="Artifact path (absolute or workspace-relative)")):
    """Serve artifact binary files (PDF/PNG/MP3/etc) inline with correct Content-Type.

    Mirror of db.read_artifact_file resolve logic (workspace_root + 'tasks/' anchor
    for legacy absolute Mac paths from other machines). Reuses _asset_mime_allowed
    whitelist from project_asset for consistency.
    """
    p = Path(path)
    if not p.is_absolute():
        p = _WORKSPACE_ROOT / p
    resolved = p.resolve()
    root_resolved = _WORKSPACE_ROOT.resolve()
    if not resolved.is_relative_to(root_resolved):
        parts = Path(path).parts
        if "tasks" in parts:
            idx = parts.index("tasks")
            candidate = _WORKSPACE_ROOT / Path(*parts[idx:])
            resolved = candidate.resolve()
        if not resolved.is_relative_to(root_resolved):
            raise HTTPException(status_code=400, detail=f"Path escapes workspace root: {path}")

    if not resolved.exists() or not resolved.is_file():
        raise HTTPException(status_code=404, detail=f"Artifact not found: {path}")

    media_type, _ = mimetypes.guess_type(str(resolved))
    if not media_type:
        media_type = "application/octet-stream"

    if not _asset_mime_allowed(media_type):
        raise HTTPException(status_code=415, detail=f"MIME type not allowed: {media_type}")

    return FileResponse(path=str(resolved), media_type=media_type)


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


# ── Galaxy graph (task vschk-flow-ui--649 block 1) ──────────────────────

@app.get("/api/galaxy/graph.json", response_model=GalaxyGraphOut)
def galaxy_graph_endpoint(
    level: int = Query(1, ge=1, le=2, description="1 = projects+tasks, 2 = +artifacts"),
) -> GalaxyGraphOut:
    """3D graph payload: nodes + edges + meta. Level 1 ~1500 nodes, Level 2 ~21K."""
    return GalaxyGraphOut(**galaxy.galaxy_graph(CFG.paths.routing_db, CFG.paths.projects_yml, level=level))


# ── Galaxy frontend page (task vschk-flow-ui--649 block 2) ──────────────

@app.get("/galaxy")
def galaxy_page(request: Request):
    """Fullscreen 3D visualization of the workspace. Chrome-less by design."""
    return templates.TemplateResponse(request, "galaxy.html", {})
