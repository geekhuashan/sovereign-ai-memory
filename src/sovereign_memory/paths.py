from __future__ import annotations

import os
from pathlib import Path


def private_dir() -> Path:
    """Per-user runtime storage, independent of the package installation."""
    if "SAM_PRIVATE_DIR" in os.environ:
        return Path(os.environ["SAM_PRIVATE_DIR"]).expanduser()
    xdg = Path(os.environ.get("XDG_DATA_HOME", ""))
    data_home = xdg if xdg.is_absolute() else Path.home() / ".local" / "share"
    return data_home / "sovereign-ai-memory"


def memory_root() -> Path:
    return Path(os.environ.get("SAM_MEMORY_ROOT", private_dir() / "memory")).expanduser()


def archive_root() -> Path:
    return Path(
        os.environ.get("SAM_ARCHIVE_ROOT", private_dir() / "raw-archive")
    ).expanduser()


def source_roots() -> dict[str, Path]:
    home = Path.home()
    return {
        "codex": Path(
            os.environ.get("SAM_CODEX_ROOT", home / ".codex" / "sessions")
        ).expanduser(),
        "claude": Path(
            os.environ.get("SAM_CLAUDE_ROOT", home / ".claude" / "projects")
        ).expanduser(),
        "grok": Path(
            os.environ.get("SAM_GROK_ROOT", home / ".grok" / "sessions")
        ).expanduser(),
    }
