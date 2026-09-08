from __future__ import annotations

from abc import ABC, abstractmethod
import hashlib
import io
from pathlib import Path
from typing import Iterable

from ..models import ParsedSession


class Adapter(ABC):
    vendor: str

    @abstractmethod
    def discover(self, root: Path) -> Iterable[Path]:
        raise NotImplementedError

    @abstractmethod
    def parse(self, path: Path, root: Path) -> ParsedSession:
        raise NotImplementedError


def relative_source_ref(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.name


def text_from_blocks(content: object, allowed_types: set[str]) -> str:
    if isinstance(content, str):
        return content.strip()
    if not isinstance(content, list):
        return ""
    parts: list[str] = []
    for block in content:
        if not isinstance(block, dict) or block.get("type") not in allowed_types:
            continue
        text = block.get("text")
        if isinstance(text, str) and text.strip():
            parts.append(text.strip())
    return "\n\n".join(parts)


def source_snapshot(path: Path) -> tuple[str, io.StringIO]:
    """Hash and parse the exact same captured bytes, even if a writer appends."""
    data = path.read_bytes()
    return hashlib.sha256(data).hexdigest(), io.StringIO(data.decode("utf-8", errors="replace"))
