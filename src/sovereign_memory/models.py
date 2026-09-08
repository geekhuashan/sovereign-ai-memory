from __future__ import annotations

from dataclasses import asdict, dataclass, field
import hashlib
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class CanonicalMessage:
    id: str
    vendor: str
    source_id: str
    session_id: str
    timestamp: str | None
    role: str
    text: str
    source_ref: str
    source_sha256: str
    metadata: dict[str, Any] = field(default_factory=dict)
    schema_version: int = 1

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ParsedSession:
    vendor: str
    source_id: str
    session_id: str
    source_path: Path
    source_ref: str
    source_sha256: str
    messages: list[CanonicalMessage]
    metadata: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stable_message_id(
    vendor: str,
    session_id: str,
    source_ref: str,
    role: str,
    text: str,
) -> str:
    material = "\0".join((vendor, session_id, source_ref, role, text))
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:32]


def stable_source_id(vendor: str, source_ref: str) -> str:
    material = f"{vendor}\0{source_ref}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:24]
