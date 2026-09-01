"""
shares_api.py — FastAPI endpoints for external public share portal (task 664).

Security-critical:
- Token validation via app.shares.get_share_by_token
- Path isolation: caller sees ONLY files in share folder (path traversal protected)
- No listing endpoint of all shares (admin-only via CLI)

Difference from partners_api:
- Public wide audience (not trusted personal)
- +asset endpoint for binary files (FileResponse + mimetypes)
- +zip endpoint for full folder download (StreamingResponse + zipfile)
- log_visit called from main.py:/share/{token}/ (HTML shell, not API)
- log_download called from /api/shares/{token}/zip

Endpoints:
  GET  /api/shares/{token}/info         → share metadata (title, description)
  GET  /api/shares/{token}/tree         → list of files/folders under share folder
  GET  /api/shares/{token}/file?path=X  → text content of .md/.txt (413 on binary)
  GET  /api/shares/{token}/asset?path=X → binary FileResponse (PNG/JPG/WebP/etc)
  GET  /api/shares/{token}/zip          → StreamingResponse application/zip of whole folder
"""

from __future__ import annotations

import io
import mimetypes
import zipfile
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from . import shares
from .config import Config


router = APIRouter(prefix="/api/shares", tags=["shares"])


class ShareInfoOut(BaseModel):
    code: str
    title: str
    description: Optional[str] = None
    view_count: int
    download_count: int


class ShareFileEntryOut(BaseModel):
    name: str
    path: str
    is_dir: bool
    size: Optional[int] = None


class ShareFileContentOut(BaseModel):
    path: str
    name: str
    content: str
    size: int


def _resolve_share_folder(cfg: Config, share: dict) -> Path:
    """Resolve absolute filesystem folder for a share."""
    if not cfg.paths.external_shares_root:
        raise HTTPException(500, "external_shares_root not configured")
    folder_path = share.get("folder_path") or share.get("code") or ""
    base = Path(cfg.paths.external_shares_root).expanduser().resolve()
    return (base / folder_path).resolve()


def _validate_and_resolve_path(share_folder: Path, requested_path: str) -> Path:
    """
    Safely resolve requested_path against share_folder.

    Prevents path traversal via `../` — resolved path MUST be inside
    share_folder. Raises HTTPException(403) if not.
    """
    requested = requested_path.lstrip("/").lstrip(".")
    if not requested:
        return share_folder

    candidate = (share_folder / requested).resolve()

    try:
        candidate.relative_to(share_folder)
    except ValueError:
        raise HTTPException(
            status_code=403,
            detail="Access denied: path outside share folder",
        )

    return candidate


def _get_share_or_404(cfg: Config, token: str) -> dict:
    """Load share by magic-token OR human code (slug). 404 if not found / inactive / expired."""
    if not cfg.paths.external_shares_db:
        raise HTTPException(500, "external_shares_db not configured")
    share = shares.get_share_by_token_or_code(
        Path(cfg.paths.external_shares_db).expanduser(), token
    )
    if not share:
        raise HTTPException(404, "Invalid or expired share link")
    return share


def _client_info(request: Request) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """Extract (ip, user_agent, referer) from request for logging."""
    ip = request.client.host if request.client else None
    # Trust X-Forwarded-For if behind nginx (real client IP)
    xff = request.headers.get("x-forwarded-for")
    if xff:
        ip = xff.split(",")[0].strip()
    ua = request.headers.get("user-agent")
    ref = request.headers.get("referer")
    return ip, ua, ref


def register_routes(app, cfg: Config) -> None:
    """Register external share routes on the given FastAPI app."""

    @router.get("/{token}/info", response_model=ShareInfoOut)
    def share_info(token: str) -> ShareInfoOut:
        share = _get_share_or_404(cfg, token)
        return ShareInfoOut(
            code=share["code"],
            title=share["title"],
            description=share.get("description"),
            view_count=share["view_count"],
            download_count=share["download_count"],
        )

    @router.get("/{token}/tree", response_model=list[ShareFileEntryOut])
    def share_tree(
        token: str, path: str = Query("", description="Subpath under share folder")
    ) -> list[ShareFileEntryOut]:
        share = _get_share_or_404(cfg, token)
        share_folder = _resolve_share_folder(cfg, share)

        if not share_folder.exists():
            raise HTTPException(404, "Share folder not found on disk")

        target = _validate_and_resolve_path(share_folder, path)
        if not target.exists():
            raise HTTPException(404, f"Path not found: {path}")
        if not target.is_dir():
            raise HTTPException(400, f"Path is not a directory: {path}")

        entries = []
        for child in sorted(target.iterdir()):
            if child.name.startswith("."):
                continue
            rel_path = str(child.relative_to(share_folder))
            entries.append(
                ShareFileEntryOut(
                    name=child.name,
                    path=rel_path,
                    is_dir=child.is_dir(),
                    size=child.stat().st_size if child.is_file() else None,
                )
            )
        return entries

    @router.get("/{token}/file", response_model=ShareFileContentOut)
    def share_file(
        token: str,
        path: str = Query(..., description="Relative path to file"),
    ) -> ShareFileContentOut:
        share = _get_share_or_404(cfg, token)
        share_folder = _resolve_share_folder(cfg, share)

        if not share_folder.exists():
            raise HTTPException(404, "Share folder not found on disk")

        target = _validate_and_resolve_path(share_folder, path)
        if not target.exists() or not target.is_file():
            raise HTTPException(404, f"File not found: {path}")

        max_size = cfg.filesystem.max_file_size_kb * 1024
        size = target.stat().st_size
        if size > max_size:
            raise HTTPException(413, f"File too large: {size} > {max_size} bytes")

        try:
            content = target.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            raise HTTPException(415, "Binary files not supported here — use /asset endpoint")

        rel_path = str(target.relative_to(share_folder))
        return ShareFileContentOut(
            path=rel_path,
            name=target.name,
            content=content,
            size=size,
        )

    @router.api_route("/{token}/asset", methods=["GET", "HEAD"])
    def share_asset(
        token: str,
        path: str = Query(..., description="Relative path to binary asset (image/pdf/etc)"),
    ):
        """Serve binary assets (PNG/JPG/WebP/PDF/etc) with correct Content-Type."""
        share = _get_share_or_404(cfg, token)
        share_folder = _resolve_share_folder(cfg, share)

        if not share_folder.exists():
            raise HTTPException(404, "Share folder not found on disk")

        target = _validate_and_resolve_path(share_folder, path)
        if not target.exists() or not target.is_file():
            raise HTTPException(404, f"Asset not found: {path}")

        # Guess mime type from filename; fallback to octet-stream
        media_type, _ = mimetypes.guess_type(str(target))
        if not media_type:
            media_type = "application/octet-stream"

        # NB: Passing `filename` to FileResponse implicitly sets
        # Content-Disposition: attachment, which tells crawlers to DOWNLOAD
        # not render — breaks OG image preview cards in TG/FB/iMessage.
        # Fix: omit filename → default inline disposition.
        return FileResponse(
            path=str(target),
            media_type=media_type,
        )

    @router.get("/{token}/zip")
    def share_zip(token: str, request: Request):
        """Stream whole share folder as a zip file. Logs download event."""
        share = _get_share_or_404(cfg, token)
        share_folder = _resolve_share_folder(cfg, share)

        if not share_folder.exists():
            raise HTTPException(404, "Share folder not found on disk")

        # Build zip in-memory (MVP: shares < 100MB assumed)
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in share_folder.rglob("*"):
                if f.is_file() and not f.name.startswith("."):
                    arcname = f.relative_to(share_folder)
                    zf.write(f, arcname)
        buf.seek(0)

        # Log download event
        ip, ua, ref = _client_info(request)
        shares.log_download(
            Path(cfg.paths.external_shares_db).expanduser(),
            share_id=share["id"],
            ip_address=ip,
            user_agent=ua,
            referer=ref,
        )

        filename = f"{share['code']}.zip"
        return StreamingResponse(
            buf,
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    app.include_router(router)
