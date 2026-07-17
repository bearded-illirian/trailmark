"""
projects.py — projects.yml parser.

Reads canonical project registry from vschk-platform/projects.yml.
Returns typed Project objects; nested sections (brand, libraries,
skills, guides) live in Project.extras as raw dicts.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml


@dataclass
class SkillPack:
    id: str
    description: Optional[str]
    skills: list[str] = field(default_factory=list)
    no_inject: bool = False


@dataclass
class Project:
    id: str
    name: str
    path: Optional[Path]
    domain: Optional[str]
    status: str
    vds_visible: bool = True
    deploy_dir_vds: Optional[Path] = None
    extras: dict[str, Any] = field(default_factory=dict)


@dataclass
class ProjectsRegistry:
    tasks_root: Optional[Path]
    skill_packs: list[SkillPack] = field(default_factory=list)
    projects: list[Project] = field(default_factory=list)


def parse_projects(yml_path: Path) -> ProjectsRegistry:
    with open(yml_path, encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    tasks_root_raw = raw.get("tasks_root")
    tasks_root = Path(tasks_root_raw).expanduser() if tasks_root_raw else None

    skill_packs = [
        SkillPack(
            id=sp["id"],
            description=sp.get("description"),
            skills=list(sp.get("skills", [])),
            no_inject=bool(sp.get("no_inject", False)),
        )
        for sp in (raw.get("skill_packs") or [])
    ]

    projects: list[Project] = []
    for p in raw.get("projects") or []:
        if "id" not in p:
            continue
        path_raw = p.get("path")
        if not path_raw:
            print(f"[projects.yml] skipping '{p['id']}' — no path field", file=sys.stderr)
            continue
        known = {"id", "name", "path", "domain", "status", "vds_visible", "deploy_dir_vds"}
        deploy_raw = p.get("deploy_dir_vds")
        projects.append(
            Project(
                id=p["id"],
                name=p.get("name", p["id"]),
                path=Path(path_raw).expanduser(),
                domain=p.get("domain"),
                status=p.get("status", "active"),
                vds_visible=bool(p.get("vds_visible", True)),
                deploy_dir_vds=Path(deploy_raw) if deploy_raw else None,
                extras={k: v for k, v in p.items() if k not in known},
            )
        )

    return ProjectsRegistry(
        tasks_root=tasks_root,
        skill_packs=skill_packs,
        projects=projects,
    )


def active_only(projects: list[Project]) -> list[Project]:
    return [p for p in projects if p.status == "active"]


def vds_visible_only(projects: list[Project]) -> list[Project]:
    return [p for p in projects if p.vds_visible]
