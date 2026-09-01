"""
portals_api.py — FastAPI admin-side WRITE endpoints for magic-link portals.

Sibling of partners_api.py (READ-side, reader opens portal via /api/partner/{token}/*).
This module handles WRITE operations invoked by Radar OS mode `extranet_portals`
(task radar-os--666, Wave 7) — create/update portals, symlink material layout.

Endpoints (this module — Block 7001 only):
  POST /api/portal/upsert   → create/update portal + folder + symlinks
                              Returns {magic_token, external_url}

Deferred to later blocks:
  POST /api/portal/rotate   → Block 7002 (new magic_token)
  GET  /api/portal/stats    → Block 7003 (view/download counters)
  HMAC Bearer auth          → Block 7004 (until then endpoint open,
                              nginx limits external access)

Idempotency: upsert preserves magic_token for existing partner code —
existing live magic-link URLs never break on repeat invocation.

Symlink layout: portals/{portal_type}/{code}/{basename} → portals/{portal_type}/{material_path}
Cleanup on re-upsert: removes only Path.is_symlink() children — physical files
(e.g. Sansan/Гефт legacy dirs "Партнёрка"/"Продажи") never touched.

Task: radar-os--666-client-portals-mode, Block 7001.
Reference: partners_api.py (READ-side pattern), shares_api.py (register_routes shape).
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import json
import os
import re
import time
from pathlib import Path
from typing import Awaitable, Callable, Optional

logger = logging.getLogger(__name__)

import secrets
import urllib.request
import urllib.error

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from . import partners
from .config import Config


router = APIRouter(prefix="/api/portal", tags=["portal-admin"])

# Viewer-facing router (без HMAC dependency — public endpoints)
# Used for /portal/{magic_token}/material/{material_id}/open — magic-link
# viewer clicks, which redirect to actual publish_url from radar-os.

# MVP hardcoded — mirror pattern from main.py (share_url / preview_image_url).
# Refactor into cfg when Block 7002 (rotate) needs same URL construction.
# Canonical portal address, task 695 block 23.
#
# History worth keeping, because this constant was wrong twice:
#   /partner  — original. Named the audience wrong: of 12 live portals 8 are clients,
#               2 students, 2 partners. Still served as a permanent redirect (block 21).
#   /portal   — my mistake in 3fc0fa6. Seeing "Partner folder not found on disk" for an
#               extranet portal, I concluded /partner was legacy and pointed links at the
#               simplified block-20020 viewer. The real cause was different: extranet
#               materials live in the portal_materials junction and in the tenant's cloud,
#               not as folders on our disk — so the file-tree portal had nothing to show.
#   /extranet — correct. One address for every external recipient, served by the real
#               showcase with a tree and inline rendering.
#
# Consumed by upsert (link issued at creation) and rotate (link reissued on token
# rotation) — a wrong value here reaches people through both paths.
_PORTAL_URL_PREFIX = "https://flow.vschk.online/extranet"

# ─────────────────────────────────────────────────────────────────────
# HMAC-SHA256 middleware (task 666 Block 11002)
# ─────────────────────────────────────────────────────────────────────
# Signature scheme (per research-doc-11000.md §Decision):
#   canonical = METHOD + "\n" + PATH + "\n" + TS + "\n" + NONCE + "\n" + BODY_CANONICAL
#   sig       = hmac_sha256(SECRET, canonical).hexdigest()  # 64 hex chars
#   Header    = "Authorization: HMAC-SHA256 ts=<unix>,nonce=<hex32>,sig=<hex64>"
# Body canonicalization (JSON POST):
#   json.dumps(payload, sort_keys=True, separators=(',',':'), ensure_ascii=False).encode('utf-8')
# For GET (no body): BODY_CANONICAL = b"".
# Timestamp window: 300 seconds. Nonce dedupe TTL: 300 seconds (in-memory dict).

_HMAC_TS_WINDOW: int = 300
_HMAC_NONCE_TTL: float = 300.0
_HMAC_HEADER_RE = re.compile(
    r"^HMAC-SHA256\s+ts=(?P<ts>\d+),nonce=(?P<nonce>[0-9a-f]{32}),sig=(?P<sig>[0-9a-f]{64})$"
)

# Module-level nonce dedupe store: nonce → expiry_ts (unix seconds).
# Single-worker uvicorn assumption verified (systemctl cat vschk-flow-ui ExecStart no --workers flag).
_NONCE_STORE: dict[str, float] = {}


def _canonicalize_body(raw: bytes) -> bytes:
    """Re-serialize JSON body to canonical bytes (sorted keys, no whitespace, UTF-8).

    Empty body → empty bytes (used for GET endpoints without JSON payload).
    Invalid JSON → raise ValueError (caught in verify, mapped to 400).
    """
    if not raw:
        return b""
    parsed = json.loads(raw)
    return json.dumps(
        parsed,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _cleanup_nonces(now: float) -> None:
    """Drop expired nonce entries. O(N) scan, acceptable for MVP scale."""
    expired = [n for n, exp in _NONCE_STORE.items() if exp < now]
    for n in expired:
        _NONCE_STORE.pop(n, None)


def _verify_hmac_signature_factory(
    secret: str,
) -> Callable[[Request], Awaitable[None]]:
    """Build FastAPI async dependency that verifies HMAC-SHA256 signature.

    Closure captures secret at register_routes call time (after systemd
    EnvironmentFile loaded PORTAL_HMAC_SECRET on service boot).

    Raises HTTPException(401, detail='invalid HMAC: <reason>') on any failure.
    Reason codes: missing_header, bad_format, bad_ts, replayed_nonce, bad_signature.
    """
    secret_bytes = secret.encode("utf-8")

    async def verify(request: Request) -> None:
        auth = request.headers.get("authorization") or request.headers.get(
            "Authorization"
        )
        if not auth:
            raise HTTPException(401, "invalid HMAC: missing_header")

        m = _HMAC_HEADER_RE.match(auth.strip())
        if not m:
            raise HTTPException(401, "invalid HMAC: bad_format")

        ts_str = m.group("ts")
        nonce = m.group("nonce")
        provided_sig = m.group("sig")

        now = time.time()
        try:
            ts = int(ts_str)
        except ValueError:
            raise HTTPException(401, "invalid HMAC: bad_ts")
        if abs(now - ts) > _HMAC_TS_WINDOW:
            raise HTTPException(401, "invalid HMAC: bad_ts")

        _cleanup_nonces(now)
        if nonce in _NONCE_STORE:
            raise HTTPException(401, "invalid HMAC: replayed_nonce")

        try:
            raw_body = await request.body()
            canonical_body = _canonicalize_body(raw_body)
        except ValueError:
            raise HTTPException(400, "invalid body: not JSON")

        canonical = (
            request.method.upper().encode("utf-8")
            + b"\n"
            + request.url.path.encode("utf-8")
            + b"\n"
            + ts_str.encode("utf-8")
            + b"\n"
            + nonce.encode("utf-8")
            + b"\n"
            + canonical_body
        )
        expected_sig = hmac.new(secret_bytes, canonical, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected_sig, provided_sig):
            raise HTTPException(401, "invalid HMAC: bad_signature")

        _NONCE_STORE[nonce] = now + _HMAC_NONCE_TTL

    return verify


class PortalUpsertIn(BaseModel):
    code: str
    name: str
    tg_handle: Optional[str] = None
    email: Optional[str] = None  # accepted but not stored (Radar-side metadata only)
    portal_type: str = "partner"
    # task 695 block 32 — tenant that owns the catalogue behind this portal.
    # Optional: the 11 file-based portals post without it and must keep working.
    # Without it the showcase cannot ask Radar OS to resolve material content.
    tenant_code: Optional[str] = None
    material_paths: list[str] = []  # legacy — physical symlink paths (Sansan/Гефт)
    # None означает «поле не прислали» и включает файловую ветку ниже; пустой
    # список означает «прислали, и он пуст» — портал надо очистить. До задачи 675
    # блока 14090 оба случая были одним значением [], и последний материал у
    # клиента убрать было физически нечем: архивация делала список пустым, а
    # пустой список читался как «эта ветка не используется».
    materials: Optional[list[dict]] = None  # W20 block 20009 — [{material_id, name, size, mime, sort_order?, folder_id?}]
    # task 695 block 72000 — папки портала [{folder_id, title, sort_order}].
    # Едут отдельным списком, потому что пустую папку прицепить не к чему, а
    # завести её заранее — прямое требование (decision-16). Приезжают той же
    # посылкой, что и материалы: рассинхрона «папки есть, материалов нет» быть
    # не должно.
    folders: Optional[list[dict]] = None


class PortalUpsertOut(BaseModel):
    code: str
    magic_token: str
    external_url: str
    is_new: bool
    materials_linked: int


class PortalRotateIn(BaseModel):
    code: str


class PortalRotateOut(BaseModel):
    code: str
    new_magic_token: str
    new_external_url: str


class PortalStatsItem(BaseModel):
    code: str
    view_count: int = 0
    download_count: int = 0
    last_visit_at: Optional[str] = None


def _ensure_task_source(portal_folder: Path) -> None:
    """Завести папку и схему задач портала. Идемпотентно."""
    from .kits.task_engine.task_engine_router import ensure_task_schema

    import sqlite3

    db = portal_folder / ".kit-data" / "tasks.sqlite"
    db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db))
    try:
        ensure_task_schema(conn)
    finally:
        conn.close()


def _resolve_portals_root(cfg: Config) -> Path:
    """Get portals root directory (portals/{type}/{code}/ layout)."""
    if not cfg.paths.portals_root:
        raise HTTPException(500, "portals_root not configured")
    return Path(cfg.paths.portals_root).expanduser().resolve()


def _layout_portal_symlinks(
    portal_folder: Path,
    material_paths: list[str],
    portals_root: Path,
    portal_type: str,
) -> int:
    """Layout symlinks in portal_folder for given material_paths.

    Steps:
      1. mkdir portal_folder if not exists
      2. Cleanup: remove existing children that are symlinks (physical files preserved)
      3. For each material_path: create symlink portal_folder/{basename} → portals_root/portal_type/{material_path}

    Returns count of symlinks created.

    Safety: physical files (non-symlink children) never touched. Protects legacy
    partners like Sansan/Гефт with physical "Партнёрка"/"Продажи" dirs.
    """
    portal_folder.mkdir(parents=True, exist_ok=True)

    # Cleanup phase: remove ONLY symlink children (physical files/dirs untouched)
    for child in portal_folder.iterdir():
        if child.is_symlink():
            child.unlink()

    # Layout phase: create fresh symlinks
    linked = 0
    portal_type_root = portals_root / portal_type
    for mpath in material_paths:
        # Strip leading slashes + dots (path traversal protection)
        clean = mpath.lstrip("/").lstrip(".")
        if not clean:
            continue

        source = (portal_type_root / clean).resolve()
        # Safety: source MUST be inside portal_type_root
        try:
            source.relative_to(portal_type_root)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"material_path escapes portal_type root: {mpath}",
            )
        if not source.exists():
            raise HTTPException(
                status_code=400,
                detail=f"material_path source not found: {mpath}",
            )

        target = portal_folder / source.name
        # If a symlink with same name lingered — cleanup phase handled it.
        # If a physical child collides — DO NOT overwrite.
        if target.exists() and not target.is_symlink():
            raise HTTPException(
                status_code=409,
                detail=f"physical file blocks symlink target: {target.name}",
            )
        target.symlink_to(source)
        linked += 1

    return linked


def register_routes(app, cfg: Config) -> None:
    """Register portal admin routes on the given FastAPI app.

    HMAC-SHA256 middleware (Block 11002) is applied via FastAPI Depends.
    Secret loaded from PORTAL_HMAC_SECRET env at boot (systemd EnvironmentFile,
    provisioned in Block 11001). Missing secret → RuntimeError fail-fast on boot.
    """

    secret = os.getenv("PORTAL_HMAC_SECRET")
    if not secret:
        raise RuntimeError(
            "PORTAL_HMAC_SECRET env var not set — check systemd EnvironmentFile "
            "/srv/vschk/env.d/extranet_portals.env (task 666 Block 11001)"
        )
    _verify_hmac = _verify_hmac_signature_factory(secret)

    @router.post("/upsert", response_model=PortalUpsertOut)
    async def portal_upsert(
        payload: PortalUpsertIn,
        _: None = Depends(_verify_hmac),
    ) -> PortalUpsertOut:
        if not cfg.paths.partners_db:
            raise HTTPException(500, "partners_db not configured")

        # Validate required fields (Pydantic ensures presence, extra checks)
        code = payload.code.strip()
        name = payload.name.strip()
        if not code:
            raise HTTPException(400, "code is required and non-empty")
        if not name:
            raise HTTPException(400, "name is required and non-empty")

        # Upsert partner row (idempotent — preserves magic_token for existing code)
        try:
            partner_row, is_new = partners.upsert_partner(
                db_path=Path(cfg.paths.partners_db).expanduser(),
                code=code,
                name=name,
                tg_handle=payload.tg_handle,
                portal_type=payload.portal_type,
                tenant_code=payload.tenant_code,
            )
        except Exception as e:
            raise HTTPException(502, f"partners.db upsert failed: {e}")

        # W20 block 20009: new materials[] branch (radar-os push) — preferred path
        # Legacy material_paths[] preserved для Sansan/Гефт до migration 20018.
        # Папки без материалов — законный случай: портал, где заведена структура,
        # но ещё ничего не положено. Условие только по materials отправило бы
        # такой портал в файловую ветку ниже и разложило бы ему символические
        # ссылки на диске, которых у каталожного портала быть не должно.
        # Признак каталожной ветки — ПРИСЛАЛИ ли поля, а не непусты ли они.
        # Пустой список — законный состав: у портала архивировали последний
        # материал, и его надо убрать у клиента. Пока условие смотрело на
        # непустоту, такой синк уходил в файловую ветку, состав не переписывался,
        # и материал оставался у клиента навсегда (задача 675 блок 14090).
        if payload.materials is not None or payload.folders is not None:
            try:
                linked = partners.set_portal_structure(
                    db_path=Path(cfg.paths.partners_db).expanduser(),
                    partner_id=int(partner_row["id"]),
                    materials_list=payload.materials or [],
                    folders_list=payload.folders or [],
                )
            except Exception as e:
                raise HTTPException(500, f"portal_materials set failed: {e}")
        else:
            # Legacy branch — physical symlinks в portals/{portal_type}/{code}/
            portals_root = _resolve_portals_root(cfg)
            portal_folder = portals_root / payload.portal_type / partner_row["folder_path"]
            try:
                linked = _layout_portal_symlinks(
                    portal_folder=portal_folder,
                    material_paths=payload.material_paths,
                    portals_root=portals_root,
                    portal_type=payload.portal_type,
                )
            except HTTPException:
                raise
            except Exception as e:
                raise HTTPException(500, f"symlink layout failed: {e}")

        # Место для задач заводится вместе с порталом, а не при первой задаче.
        # Без этого вкладка «Задачи» открывается, выглядит рабочей и пустой, а
        # первая созданная задача падает на no such table: tasks. На 22.08.2026
        # так было у пятнадцати порталов из шестнадцати (задача 706, блок 2331).
        # Кладём только скрытую .kit-data — символических ссылок материалов у
        # каталожного портала по-прежнему не появляется.
        try:
            portals_root = _resolve_portals_root(cfg)
            _ensure_task_source(
                portals_root / payload.portal_type / partner_row["folder_path"]
            )
        except Exception as e:
            # Портал важнее вкладки задач: схему всё равно заведёт первая запись.
            logger.warning("task source bootstrap failed for %s: %s", code, e)

        magic_token = partner_row["magic_token"]
        external_url = f"{_PORTAL_URL_PREFIX}/{magic_token}/"

        return PortalUpsertOut(
            code=code,
            magic_token=magic_token,
            external_url=external_url,
            is_new=is_new,
            materials_linked=linked,
        )

    @router.post("/rotate", response_model=PortalRotateOut)
    async def portal_rotate(
        payload: PortalRotateIn,
        _: None = Depends(_verify_hmac),
    ) -> PortalRotateOut:
        if not cfg.paths.partners_db:
            raise HTTPException(500, "partners_db not configured")

        code = payload.code.strip()
        if not code:
            raise HTTPException(400, "code is required and non-empty")

        try:
            new_token = partners.rotate_partner_token(
                db_path=Path(cfg.paths.partners_db).expanduser(),
                code=code,
            )
        except Exception as e:
            raise HTTPException(502, f"partners.db rotate failed: {e}")

        if new_token is None:
            raise HTTPException(404, f"portal not found: code={code}")

        return PortalRotateOut(
            code=code,
            new_magic_token=new_token,
            new_external_url=f"{_PORTAL_URL_PREFIX}/{new_token}/",
        )

    @router.get("/stats", response_model=list[PortalStatsItem])
    async def portal_stats(
        codes: Optional[str] = Query(
            None,
            description="Optional comma-separated portal codes to filter",
        ),
        _: None = Depends(_verify_hmac),
    ) -> list[PortalStatsItem]:
        """Return per-portal stats. MVP stub — real tracking (visit/download
        logging in main.py partner_portal handler + partner_visits table)
        deferred to v2. All counters return zero until tracking implemented.

        Task: radar-os--666 Block 7003.
        v2 backlog: partner_visits/downloads tables + log_visit hooks.
        """
        if not cfg.paths.partners_db:
            raise HTTPException(500, "partners_db not configured")

        all_partners = partners.list_partners(
            db_path=Path(cfg.paths.partners_db).expanduser(),
            include_inactive=False,
        )

        filter_codes = None
        if codes:
            filter_codes = {c.strip() for c in codes.split(",") if c.strip()}

        result = []
        for p in all_partners:
            if filter_codes is not None and p["code"] not in filter_codes:
                continue
            result.append(PortalStatsItem(code=p["code"]))
        return result

    # ═══════════════════════════════════════════════════════════════
    # Viewer-facing routes (Block 20020) — magic-link landing + JSON API
    # ═══════════════════════════════════════════════════════════════

    def _viewer_partner(magic_token: str) -> dict:
        """Shared helper для viewer endpoints — lookup partner by token, 404 если нет."""
        if not cfg.paths.partners_db:
            raise HTTPException(500, "partners_db not configured")
        try:
            row = partners.get_partner_by_token(
                Path(cfg.paths.partners_db).expanduser(), magic_token
            )
        except Exception as e:
            raise HTTPException(500, f"partners lookup failed: {e}")
        if not row:
            raise HTTPException(404, "portal not found")
        return row

    # Регистрация административного роутера (/api/portal) — путь синка из Radar OS.
    # В блоке 70 эта строка была снесена вместе с клиентским viewer_router:
    # вырезка по диапазону строк захватила её на границе. Синк отвалился с 404,
    # поймано живой проверкой блока 80.
    app.include_router(router)


class _RadarResolveError(RuntimeError):
    """Raised by _call_radar_resolve on non-2xx / network failure."""


def _sign_hmac_outbound(
    secret: str, method: str, path: str, body_dict: Optional[dict]
) -> str:
    """Build HMAC-SHA256 Authorization header для outbound call to radar-os.

    Mirrors PHP extranet_portals_hmac_header() canonicalization exactly
    (recursive-sorted body + separators=(',', ':') + ensure_ascii=False).
    """
    ts = int(time.time())
    nonce = secrets.token_hex(16)
    if body_dict is None or body_dict == {}:
        canonical_body = b""
    else:
        canonical_body = json.dumps(
            body_dict, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")

    canonical = (
        method.upper().encode("utf-8")
        + b"\n"
        + path.encode("utf-8")
        + b"\n"
        + str(ts).encode("utf-8")
        + b"\n"
        + nonce.encode("utf-8")
        + b"\n"
        + canonical_body
    )
    sig = hmac.new(secret.encode("utf-8"), canonical, hashlib.sha256).hexdigest()
    return f"HMAC-SHA256 ts={ts},nonce={nonce},sig={sig}"


_RADAR_RESOLVE_URL = (
    "https://team.radar.vschk.online"
    "/radar/api/modes/extranet_portals/material_resolve_url.php"
)
_RADAR_RESOLVE_PATH = "/radar/api/modes/extranet_portals/material_resolve_url.php"
_RADAR_RESOLVE_TIMEOUT = 15.0


def _call_radar_resolve(
    tenant_code: str,
    material_id: int,
    secret: str,
    mode: str = "publish",
    projection: str = "source",
) -> dict:
    """Call radar-os material_resolve_url.php endpoint with HMAC signed request.

    Args:
      mode: 'publish' (default) → returns permanent publish_url for 302 redirect.
            'stream'            → returns short-lived signed download URL for inline embed.
      projection: 'source' (default) → сам документ.
            'page' → собранная страница рядом с ним (задача 701, decision-02).
            Материал тот же, id тот же — меняется только представление.

    Returns parsed JSON response dict.
      publish mode: {ok, publish_url, mime, size, from_cache}
      stream mode:  {ok, stream_url, expires_hint, mime, size, from_cache:false}
    Raises _RadarResolveError on network / non-2xx / non-JSON.
    """
    body_dict = {
        "tenant_code": tenant_code,
        "material_id": material_id,
        "mode": mode,
        "projection": projection,
    }
    body_bytes = json.dumps(
        body_dict, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    auth_header = _sign_hmac_outbound(secret, "POST", _RADAR_RESOLVE_PATH, body_dict)

    req = urllib.request.Request(
        _RADAR_RESOLVE_URL,
        data=body_bytes,
        headers={
            "Content-Type": "application/json",
            "Authorization": auth_header,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=_RADAR_RESOLVE_TIMEOUT) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as e:
        try:
            err_body = e.read().decode("utf-8", errors="replace")
        except Exception:
            err_body = ""
        raise _RadarResolveError(f"HTTP {e.code}: {err_body[:300]}")
    except urllib.error.URLError as e:
        raise _RadarResolveError(f"network: {e.reason}")

    try:
        parsed = json.loads(raw)
    except Exception as e:
        raise _RadarResolveError(f"non-JSON response: {e}")

    if not isinstance(parsed, dict) or not parsed.get("ok"):
        err = parsed.get("error", "UNKNOWN") if isinstance(parsed, dict) else "PARSE_ERR"
        raise _RadarResolveError(f"radar-os returned not-ok: {err}")

    return parsed
