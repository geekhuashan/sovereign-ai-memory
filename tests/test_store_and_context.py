from __future__ import annotations

from pathlib import Path
import tempfile
import sqlite3
import unittest

from sovereign_memory.context import build_context_pack
from sovereign_memory.models import CanonicalMessage, ParsedSession
from sovereign_memory.redact import redact_secrets
from sovereign_memory.store import MemoryStore


class StoreAndContextTests(unittest.TestCase):
    def test_ingest_search_reimport_and_context_redaction(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            memory_root = root / "memory"
            (memory_root / "core").mkdir(parents=True)
            (memory_root / "core" / "identity.md").write_text(
                "# Identity\n\nOwner of the memory.\n", encoding="utf-8"
            )
            source = root / "source.jsonl"
            source.write_text("fixture\n", encoding="utf-8")
            message = CanonicalMessage(
                id="a" * 32,
                vendor="codex",
                source_id="source-1",
                session_id="session-1",
                timestamp="2026-01-01T00:00:00Z",
                role="user",
                text="sovereign memory token=supersecretvalue",
                source_ref="source.jsonl#1",
                source_sha256="b" * 64,
            )
            session = ParsedSession(
                vendor="codex",
                source_id="source-1",
                session_id="session-1",
                source_path=source,
                source_ref="source.jsonl",
                source_sha256="b" * 64,
                messages=[message],
            )
            store = MemoryStore(root / ".private")
            store.ingest(session)
            store.ingest(session)

            second_message = CanonicalMessage(
                id="c" * 32,
                vendor="codex",
                source_id="source-2",
                session_id="session-1",
                timestamp="2026-01-02T00:00:00Z",
                role="user",
                text="sovereign memory token=supersecretvalue",
                source_ref="source-2.jsonl#1",
                source_sha256="d" * 64,
            )
            second_session = ParsedSession(
                vendor="codex",
                source_id="source-2",
                session_id="session-1",
                source_path=source,
                source_ref="source-2.jsonl",
                source_sha256="d" * 64,
                messages=[second_message],
            )
            store.ingest(second_session)

            self.assertEqual(store.counts(), {"sessions": 2, "messages": 2})
            results = store.search("sovereign", 5)
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0]["text"], message.text)
            pack = build_context_pack("sovereign", store, memory_root)
            self.assertIn("Owner of the memory", pack)
            self.assertIn("token=[REDACTED]", pack)
            self.assertNotIn("supersecretvalue", pack)

    def test_legacy_database_is_not_silently_deleted(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with sqlite3.connect(root / "index.sqlite3") as connection:
                connection.execute("CREATE TABLE sessions (valuable TEXT)")
                connection.execute("INSERT INTO sessions VALUES ('preserve')")
            with self.assertRaises(ValueError):
                MemoryStore(root).initialize()
            with sqlite3.connect(root / "index.sqlite3") as connection:
                self.assertEqual(connection.execute("SELECT valuable FROM sessions").fetchone()[0], "preserve")

    def test_tiny_context_budget_is_respected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pack = build_context_pack("hello", MemoryStore(root), root / "memory", max_chars=12)
            self.assertLessEqual(len(pack), 12)

    def test_common_secret_redaction(self) -> None:
        value = "credential sk-proj-" + "abcdefghijklmnopqrstuvwxyz123456"
        self.assertNotIn("abcdefghijklmnopqrstuvwxyz", redact_secrets(value))


if __name__ == "__main__":
    unittest.main()
