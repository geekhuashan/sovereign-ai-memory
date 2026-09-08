from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from .base import Adapter, relative_source_ref, text_from_blocks, source_snapshot
from ..models import (
    CanonicalMessage,
    ParsedSession,
    stable_message_id,
    stable_source_id,
)


class CodexAdapter(Adapter):
    vendor = "codex"

    def discover(self, root: Path) -> Iterable[Path]:
        return sorted(path for path in root.rglob("*.jsonl") if path.is_file())

    def parse(self, path: Path, root: Path) -> ParsedSession:
        source_ref = relative_source_ref(path, root)
        source_hash, snapshot = source_snapshot(path)
        source_id = stable_source_id(self.vendor, source_ref)
        current_session_id = path.stem
        primary_session_id: str | None = None
        session_ids: list[str] = []
        metadata: dict[str, object] = {}
        messages: list[CanonicalMessage] = []
        warnings: list[str] = []

        with snapshot as handle:
            for line_number, line in enumerate(handle, 1):
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    warnings.append(f"line {line_number}: invalid JSON")
                    continue
                if not isinstance(record, dict):
                    continue
                payload = record.get("payload")
                if not isinstance(payload, dict):
                    continue
                if record.get("type") == "session_meta":
                    candidate = payload.get("id") or payload.get("session_id")
                    if isinstance(candidate, str) and candidate:
                        current_session_id = candidate
                        if primary_session_id is None:
                            primary_session_id = candidate
                        if candidate not in session_ids:
                            session_ids.append(candidate)
                    for key in ("cwd", "cli_version", "model_provider", "source"):
                        value = payload.get(key)
                        if isinstance(value, str):
                            metadata[key] = value
                    continue
                if record.get("type") != "response_item" or payload.get("type") != "message":
                    continue
                role = payload.get("role")
                if role not in {"user", "assistant"}:
                    continue
                if payload.get("channel") in {"analysis", "reasoning"}:
                    continue
                text = text_from_blocks(
                    payload.get("content"), {"input_text", "output_text"}
                )
                if not text:
                    continue
                item_metadata: dict[str, object] = {}
                phase = payload.get("phase")
                if isinstance(phase, str):
                    item_metadata["phase"] = phase
                timestamp = record.get("timestamp")
                messages.append(
                    self._message(
                        source_id,
                        current_session_id,
                        source_ref,
                        source_hash,
                        line_number,
                        timestamp if isinstance(timestamp, str) else None,
                        role,
                        text,
                        item_metadata,
                    )
                )

        metadata["session_ids"] = session_ids
        return ParsedSession(
            vendor=self.vendor,
            source_id=source_id,
            session_id=primary_session_id or current_session_id,
            source_path=path,
            source_ref=source_ref,
            source_sha256=source_hash,
            messages=messages,
            metadata=metadata,
            warnings=warnings,
        )

    def _message(
        self,
        source_id: str,
        session_id: str,
        source_file_ref: str,
        source_hash: str,
        line_number: int,
        timestamp: str | None,
        role: str,
        text: str,
        metadata: dict[str, object],
    ) -> CanonicalMessage:
        source_ref = f"{source_file_ref}#{line_number}"
        return CanonicalMessage(
            id=stable_message_id(self.vendor, session_id, source_ref, role, text),
            vendor=self.vendor,
            source_id=source_id,
            session_id=session_id,
            timestamp=timestamp,
            role=role,
            text=text,
            source_ref=source_ref,
            source_sha256=source_hash,
            metadata=metadata,
        )
