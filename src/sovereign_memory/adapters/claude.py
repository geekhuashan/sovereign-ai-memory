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


class ClaudeAdapter(Adapter):
    vendor = "claude"

    def discover(self, root: Path) -> Iterable[Path]:
        # Main sessions are one level below the encoded project directory.
        # `subagents/` logs are operational traces, not user chat history.
        return sorted(path for path in root.glob("*/*.jsonl") if path.is_file())

    def parse(self, path: Path, root: Path) -> ParsedSession:
        source_file_ref = relative_source_ref(path, root)
        source_hash, snapshot = source_snapshot(path)
        source_id = stable_source_id(self.vendor, source_file_ref)
        current_session_id = path.stem
        primary_session_id: str | None = None
        session_ids: list[str] = []
        metadata: dict[str, object] = {}
        pending: list[
            tuple[int, str, str | None, str, str, dict[str, object]]
        ] = []
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
                record_type = record.get("type")
                if record_type not in {"user", "assistant"}:
                    continue
                if record.get("isSidechain") is True:
                    continue
                candidate = record.get("sessionId")
                if isinstance(candidate, str) and candidate:
                    current_session_id = candidate
                    if primary_session_id is None:
                        primary_session_id = candidate
                    if candidate not in session_ids:
                        session_ids.append(candidate)
                cwd = record.get("cwd")
                if isinstance(cwd, str):
                    metadata["cwd"] = cwd
                message = record.get("message")
                if not isinstance(message, dict):
                    continue
                role = message.get("role")
                if role is None:
                    role = record_type
                if role not in {"user", "assistant"}:
                    continue
                text = text_from_blocks(message.get("content"), {"text"})
                if not text:
                    continue
                item_metadata: dict[str, object] = {}
                model = message.get("model")
                if isinstance(model, str):
                    item_metadata["model"] = model
                timestamp = record.get("timestamp")
                pending.append(
                    (
                        line_number,
                        current_session_id,
                        timestamp if isinstance(timestamp, str) else None,
                        role,
                        text,
                        item_metadata,
                    )
                )

        messages: list[CanonicalMessage] = []
        for (
            line_number,
            message_session_id,
            timestamp,
            role,
            text,
            item_metadata,
        ) in pending:
            source_ref = f"{source_file_ref}#{line_number}"
            messages.append(
                CanonicalMessage(
                    id=stable_message_id(
                        self.vendor, message_session_id, source_ref, role, text
                    ),
                    vendor=self.vendor,
                    source_id=source_id,
                    session_id=message_session_id,
                    timestamp=timestamp,
                    role=role,
                    text=text,
                    source_ref=source_ref,
                    source_sha256=source_hash,
                    metadata=item_metadata,
                )
            )
        metadata["session_ids"] = session_ids
        return ParsedSession(
            vendor=self.vendor,
            source_id=source_id,
            session_id=primary_session_id or current_session_id,
            source_path=path,
            source_ref=source_file_ref,
            source_sha256=source_hash,
            messages=messages,
            metadata=metadata,
            warnings=warnings,
        )
