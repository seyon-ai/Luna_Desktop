"""Filesystem tools. All paths are resolved inside a scoped root (default:
the user's home) to avoid accidental writes outside the workspace; the agent
still has full-file tools, with the permission layer guarding high-impact ops.
"""

from __future__ import annotations

import os
import re
import shutil
from pathlib import Path
from typing import Any


class FileToolError(RuntimeError):
    pass


def _resolve(path: str | Path, scope: Path | None = None) -> Path:
    raw = Path(os.path.expandvars(os.path.expanduser(str(path))))
    if not raw.is_absolute() and scope is not None:
        raw = Path(scope) / raw
    p = raw.resolve()
    if scope is not None:
        scope = scope.resolve()
        try:
            p.relative_to(scope)
        except ValueError as exc:
            raise FileToolError(f"Path is outside the permitted workspace: {p}") from exc
    return p


def list_directory(path: str = ".", hidden: bool = False, scope: Path | None = None) -> dict[str, Any]:
    target = _resolve(path, scope)
    if not target.exists():
        raise FileToolError(f"Directory does not exist: {target}")
    if not target.is_dir():
        raise FileToolError(f"Not a directory: {target}")
    entries = []
    for child in sorted(target.iterdir(), key=lambda p: p.name.lower()):
        if not hidden and child.name.startswith("."):
            continue
        entries.append(
            {
                "name": child.name,
                "type": "directory" if child.is_dir() else "file",
                "size": child.stat().st_size if child.is_file() else None,
            }
        )
    return {"path": str(target), "entries": entries[:500]}


def read_file(path: str, max_bytes: int = 2_000_000, scope: Path | None = None) -> dict[str, Any]:
    target = _resolve(path, scope)
    if not target.exists():
        raise FileToolError(f"File does not exist: {target}")
    if not target.is_file():
        raise FileToolError(f"Not a file: {target}")
    size = target.stat().st_size
    data = target.read_bytes()[:max_bytes]
    try:
        text = data.decode("utf-8")
        truncated = size > max_bytes
    except UnicodeDecodeError:
        text = f"<binary file, {size} bytes>"
        truncated = False
    return {"path": str(target), "size": size, "content": text, "truncated": truncated}


def write_file(path: str, content: str, append: bool = False, scope: Path | None = None) -> dict[str, Any]:
    target = _resolve(path, scope)
    target.parent.mkdir(parents=True, exist_ok=True)
    mode = "a" if append else "w"
    with target.open(mode, encoding="utf-8") as fh:
        fh.write(content)
    return {"path": str(target), "size": target.stat().st_size, "append": append}


def create_directory(path: str, scope: Path | None = None) -> dict[str, Any]:
    target = _resolve(path, scope)
    target.mkdir(parents=True, exist_ok=True)
    return {"path": str(target), "created": True}


def move_file(source: str, destination: str, overwrite: bool = False, scope: Path | None = None) -> dict[str, Any]:
    src = _resolve(source, scope)
    dst = _resolve(destination, scope)
    if not src.exists():
        raise FileToolError(f"Source does not exist: {src}")
    if dst.exists() and not overwrite:
        raise FileToolError(f"Destination already exists: {dst}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dst))
    return {"source": str(src), "destination": str(dst)}


def delete_file(path: str, scope: Path | None = None) -> dict[str, Any]:
    target = _resolve(path, scope)
    if not target.exists():
        raise FileToolError(f"File does not exist: {target}")
    if target.is_dir():
        raise FileToolError("Use delete_directory for directories.")
    size = target.stat().st_size
    target.unlink()
    return {"path": str(target), "deleted": True, "size": size}


def delete_directory(path: str, scope: Path | None = None) -> dict[str, Any]:
    target = _resolve(path, scope)
    if not target.exists():
        raise FileToolError(f"Directory does not exist: {target}")
    if not target.is_dir():
        raise FileToolError("Not a directory.")
    shutil.rmtree(target)
    return {"path": str(target), "deleted": True}


def search_files(pattern: str, directory: str = ".", scope: Path | None = None, limit: int = 200) -> dict[str, Any]:
    target = _resolve(directory, scope)
    if not target.exists():
        raise FileToolError(f"Directory does not exist: {target}")
    rx = re.compile(pattern)
    matches = []
    for root, dirs, files in os.walk(target):
        dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("__pycache__", "node_modules")]
        for name in files:
            if rx.search(name):
                matches.append(str(Path(root) / name))
                if len(matches) >= limit:
                    break
        if len(matches) >= limit:
            break
    return {"pattern": pattern, "matches": matches}


def organize_downloads(directory: str, scope: Path | None = None) -> dict[str, Any]:
    """Group files by extension into folders (e.g. images/, documents/)."""
    target = _resolve(directory, scope)
    if not target.is_dir():
        raise FileToolError(f"Not a directory: {target}")
    grouping = {
        "images": {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".bmp"},
        "documents": {".pdf", ".doc", ".docx", ".txt", ".md", ".rtf", ".odt", ".csv", ".xls", ".xlsx", ".ppt", ".pptx"},
        "audio": {".mp3", ".wav", ".flac", ".ogg", ".m4a"},
        "video": {".mp4", ".mkv", ".avi", ".mov", ".webm"},
        "archives": {".zip", ".rar", ".7z", ".tar", ".gz", ".bz2"},
        "installers": {".exe", ".msi", ".dmg", ".deb", ".rpm", ".AppImage"},
    }
    moved: dict[str, list[str]] = {}
    for child in list(target.iterdir()):
        if not child.is_file():
            continue
        folder = next((f for f, suffixes in grouping.items() if child.suffix.lower() in suffixes), None)
        if folder is None:
            continue
        dest_dir = target / folder
        dest_dir.mkdir(exist_ok=True)
        dest = dest_dir / child.name
        if dest.exists():
            dest = dest_dir / f"{child.stem}-dup{child.suffix}"
        shutil.move(str(child), str(dest))
        moved.setdefault(folder, []).append(child.name)
    return {"directory": str(target), "moved": moved}
