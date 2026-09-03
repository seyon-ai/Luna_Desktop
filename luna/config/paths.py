"""LUNA_HOME path resolution and directory layout.

All user data lives outside the Git repository. The base directory is:

* Windows: ``%LOCALAPPDATA%\\Luna``
* Linux/macOS: ``~/.luna``

and can be overridden with the ``LUNA_HOME`` environment variable.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path


def default_luna_home() -> Path:
    """Return the platform-appropriate default LUNA home directory."""
    override = os.environ.get("LUNA_HOME")
    if override:
        return Path(override).expanduser().resolve()
    if sys.platform.startswith("win"):
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        if base:
            return Path(base) / "Luna"
        return Path.home() / "AppData" / "Local" / "Luna"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Luna"
    return Path.home() / ".luna"


@dataclass(frozen=True)
class LunaPaths:
    """Resolved LUNA_HOME layout."""

    root: Path
    models: Path
    voices: Path
    memory: Path
    tasks: Path
    logs: Path
    cache: Path
    browser_profile: Path
    config: Path

    @property
    def database(self) -> Path:
        return self.memory / "luna.db"

    @property
    def config_file(self) -> Path:
        return self.config / "config.json"

    @property
    def task_artifacts(self) -> Path:
        return self.tasks

    def ensure(self) -> "LunaPaths":
        for directory in (
            self.root,
            self.models,
            self.voices,
            self.memory,
            self.tasks,
            self.logs,
            self.cache,
            self.browser_profile,
            self.config,
        ):
            directory.mkdir(parents=True, exist_ok=True)
        return self

    def as_dict(self) -> dict[str, str]:
        return {
            "root": str(self.root),
            "models": str(self.models),
            "voices": str(self.voices),
            "memory": str(self.memory),
            "tasks": str(self.tasks),
            "logs": str(self.logs),
            "cache": str(self.cache),
            "browser_profile": str(self.browser_profile),
            "config": str(self.config),
        }


def resolve_paths(root: Path | str | None = None) -> LunaPaths:
    """Build and ensure the LUNA path layout."""
    if root is None:
        root = default_luna_home()
    base = Path(root).expanduser().resolve() if not isinstance(root, Path) else root.expanduser().resolve()
    paths = LunaPaths(
        root=base,
        models=base / "models",
        voices=base / "voices",
        memory=base / "memory",
        tasks=base / "tasks",
        logs=base / "logs",
        cache=base / "cache",
        browser_profile=base / "cache" / "browser-profile",
        config=base / "config",
    )
    return paths.ensure()
