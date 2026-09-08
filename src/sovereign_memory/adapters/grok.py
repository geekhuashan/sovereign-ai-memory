from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Iterable
from urllib.parse import unquote

from .base import Adapter, relative_source_ref, text_from_blocks, source_snapshot
from ..models import (
    CanonicalMessage,
    ParsedSession,
    stable_message_id,
    stable_source_id,
)


class GrokAdapter(Adapter):
    vendor = "grok"

    def discover(self, root: Path) -> Iterable[Path]:
        return sorted(
            path for path in root.rglob("chat_history.jsonl") if path.is_file()
        )

    def parse(self, path: Path, root: Path) -> ParsedSession:
        source_file_ref = relative_source_ref(path, root)
        source_hash, snapshot = source_snapshot(path)
        source_id = stable_source_id(self.vendor, source_file_ref)
        session_id = path.parent.name
        workspace = unquote(path.parent.parent.name)
        timestamp_fallback = datetime.fromtimestamp(
            path.stat().st_mtime, tz=timezone.utc
        ).isoformat()
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
                role = record.get("type")
                if role not in {"user", "assistant"}:
                    continue
                text = text_from_blocks(record.get("content"), {"text"})
                if not text:
                    continue
                source_ref = f"{source_file_ref}#{line_number}"
                item_metadata: dict[str, object] = {}
                model = record.get("model_id")
                if isinstance(model, str):
                    item_metadata["model"] = model
                messages.append(
                    CanonicalMessage(
                        id=stable_message_id(
                            self.vendor, session_id, source_ref, role, text
                        ),
                        vendor=self.vendor,
                        source_id=source_id,
                        session_id=session_id,
                        timestamp=None,
                        role=role,
                        text=text,
                        source_ref=source_ref,
                        source_sha256=source_hash,
                        metadata=item_metadata,
                    )
                )
        return ParsedSession(
            vendor=self.vendor,
            source_id=source_id,
            session_id=session_id,
            source_path=path,
            source_ref=source_file_ref,
            source_sha256=source_hash,
            messages=messages,
            metadata={"workspace": workspace, "source_mtime": timestamp_fallback},
            warnings=warnings,
        )
