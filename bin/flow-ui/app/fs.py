"""
fs.py — Filesystem walker for project browsing.

Read-only. Respects config.filesystem.ignore + text_extensions + max_file_size_kb.
Enforces path-traversal defense: every subpath is resolved and must live under base.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass
class FSEntry:
    name: str
    type: str  # 'file' | 'dir'
    size: int
    is_text: bool


def _safe_resolve(base: Path, subpath: str) -> Path:
    """
    Resolve subpath under base and reject any escape (symlink, ../).
    """
    base_resolved = base.expanduser().resolve()
    if not base_resolved.exists():
        raise FileNotFoundError(f"Base does not exist: {base_resolved}")
    candidate = (base_resolved / subpath.lstrip("/")).resolve()
    if not candidate.is_relative_to(base_resolved):
        raise ValueError(f"Path escapes base: {subpath}")
    return candidate


def _is_text(name: str, text_exts: Iterable[str]) -> bool:
    if "." not in name:
        return name.lower() in {"readme", "makefile", "dockerfile"}
    ext = name.rsplit(".", 1)[-1].lower()
    return ext in {e.lower() for e in text_exts}


def walk_dir(
    base: Path,
    subpath: str,
    ignore: Iterable[str],
    text_exts: Iterable[str],
) -> list[FSEntry]:
    """
    List immediate children of base/subpath. Not recursive (front-end
    lazily expands folders by calling walk_dir with a deeper subpath).
    """
    target = _safe_resolve(base, subpath)
    if not target.is_dir():
        raise NotADirectoryError(f"Not a directory: {target}")
    ignore_set = {i.strip("/") for i in ignore}
    entries: list[FSEntry] = []
    for child in sorted(target.iterdir(), key=lambda p: (p.is_file(), p.name.lower())):
        if child.name in ignore_set:
            continue
        try:
            stat = child.stat()
        except OSError:
            continue
        if child.is_dir():
            entries.append(FSEntry(name=child.name, type="dir", size=0, is_text=False))
        elif child.is_file():
            entries.append(
                FSEntry(
                    name=child.name,
                    type="file",
                    size=stat.st_size,
                    is_text=_is_text(child.name, text_exts),
                )
            )
    return entries


def read_text_file(
    base: Path,
    subpath: str,
    max_kb: int,
    text_exts: Iterable[str],
) -> str:
    target = _safe_resolve(base, subpath)
    if not target.is_file():
        raise FileNotFoundError(f"Not a file: {target}")
    if not _is_text(target.name, text_exts):
        raise ValueError(f"Not a text file (extension not in whitelist): {target.name}")
    if target.stat().st_size > max_kb * 1024:
        return target.read_text(encoding="utf-8", errors="replace")[: max_kb * 1024] + "\n\n[…truncated]"
    return target.read_text(encoding="utf-8", errors="replace")
