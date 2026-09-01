"""
config.py — YAML config loader with FLOW_UI_* env overrides.

Load order:
  1. Read YAML file (config.yml or config.example.yml)
  2. Overlay env vars matching FLOW_UI_<UPPER_SNAKE_PATH> (dot → underscore)
  3. Expand ~ in every Path field
  4. Return typed Config dataclass
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml


ENV_PREFIX = "FLOW_UI_"


@dataclass
class Paths:
    routing_db: Path
    projects_yml: Path
    projects_root: Path
    access_log: Path
    platform_db: Optional[Path] = None
    aihub_api_url: Optional[str] = None
    partners_db: Optional[Path] = None
    partner_content_root: Optional[Path] = None
    # portals_root — новый корень для portals/{type}/{code}/ layout.
    # Если задан, partners_api резолвит через portals_root/portal_type/folder_path.
    # Fallback на partner_content_root если None (legacy dev setup).
    portals_root: Optional[Path] = None
    # External shares — public magic-link engine (task 664).
    # Separate from partners: partners = trusted personal, shares = public wide-audience.
    external_shares_db: Optional[Path] = None
    external_shares_root: Optional[Path] = None


@dataclass
class Server:
    host: str = "127.0.0.1"
    port: int = 8765


@dataclass
class Brand:
    primary: str = "#F4A300"
    bg: str = "#FAFAF9"
    fg: str = "#1A1A19"


@dataclass
class UI:
    theme: str = "vschk-ai"
    brand: Brand = field(default_factory=Brand)


@dataclass
class Filesystem:
    ignore: list[str] = field(default_factory=list)
    max_file_size_kb: int = 500
    text_extensions: list[str] = field(default_factory=list)


@dataclass
class Config:
    paths: Paths
    server: Server
    ui: UI
    filesystem: Filesystem
    mode: str = "local"


def _apply_env_overrides(data: dict[str, Any], prefix: str = ENV_PREFIX) -> dict[str, Any]:
    """
    Walk env vars starting with FLOW_UI_ and overlay onto data by dot path.
    FLOW_UI_SERVER_PORT=9000 → data["server"]["port"] = "9000"
    """
    for key, value in os.environ.items():
        if not key.startswith(prefix):
            continue
        path = key[len(prefix) :].lower().split("_")
        cursor: Any = data
        for segment in path[:-1]:
            if not isinstance(cursor, dict) or segment not in cursor:
                cursor = None
                break
            cursor = cursor[segment]
        if isinstance(cursor, dict) and path[-1] in cursor:
            cursor[path[-1]] = value
    return data


def _expand(p: str | Path) -> Path:
    return Path(str(p)).expanduser().resolve()


def load_config(path: str | Path = "config.yml") -> Config:
    yml_path = Path(path).expanduser()
    if not yml_path.exists():
        example = yml_path.parent / "config.example.yml"
        if example.exists():
            yml_path = example
        else:
            raise FileNotFoundError(f"Config not found: {path} (and no config.example.yml)")

    with open(yml_path, encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    raw = _apply_env_overrides(raw)

    paths_raw = raw.get("paths", {})
    server_raw = raw.get("server", {})
    ui_raw = raw.get("ui", {})
    brand_raw = ui_raw.get("brand", {})
    fs_raw = raw.get("filesystem", {})

    platform_db_raw = paths_raw.get("platform_db")
    platform_db = _expand(platform_db_raw) if platform_db_raw else None

    aihub_api_url_raw = paths_raw.get("aihub_api_url")
    aihub_api_url = aihub_api_url_raw or None  # empty string → None

    partners_db_raw = paths_raw.get("partners_db")
    partners_db = _expand(partners_db_raw) if partners_db_raw else None

    partner_content_root_raw = paths_raw.get("partner_content_root")
    partner_content_root = (
        _expand(partner_content_root_raw) if partner_content_root_raw else None
    )

    portals_root_raw = paths_raw.get("portals_root")
    portals_root = _expand(portals_root_raw) if portals_root_raw else None

    external_shares_db_raw = paths_raw.get("external_shares_db")
    external_shares_db = _expand(external_shares_db_raw) if external_shares_db_raw else None

    external_shares_root_raw = paths_raw.get("external_shares_root")
    external_shares_root = _expand(external_shares_root_raw) if external_shares_root_raw else None

    return Config(
        paths=Paths(
            routing_db=_expand(paths_raw["routing_db"]),
            projects_yml=_expand(paths_raw["projects_yml"]),
            projects_root=_expand(paths_raw["projects_root"]),
            access_log=_expand(paths_raw["access_log"]),
            platform_db=platform_db,
            aihub_api_url=aihub_api_url,
            partners_db=partners_db,
            partner_content_root=partner_content_root,
            portals_root=portals_root,
            external_shares_db=external_shares_db,
            external_shares_root=external_shares_root,
        ),
        server=Server(
            host=server_raw.get("host", "127.0.0.1"),
            port=int(server_raw.get("port", 8765)),
        ),
        ui=UI(
            theme=ui_raw.get("theme", "vschk-ai"),
            brand=Brand(
                primary=brand_raw.get("primary", "#F4A300"),
                bg=brand_raw.get("bg", "#FAFAF9"),
                fg=brand_raw.get("fg", "#1A1A19"),
            ),
        ),
        filesystem=Filesystem(
            ignore=list(fs_raw.get("ignore", [])),
            max_file_size_kb=int(fs_raw.get("max_file_size_kb", 500)),
            text_extensions=list(fs_raw.get("text_extensions", [])),
        ),
        mode=str(raw.get("mode", "local")),
    )


if __name__ == "__main__":
    cfg = load_config("config.example.yml")
    print(cfg)
