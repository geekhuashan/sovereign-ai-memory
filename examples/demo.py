#!/usr/bin/env python3
"""Run the real CLI against fabricated sessions in a temporary directory.

This script does not read your AI history, call a model, or retain demo data.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def write_records(destination: Path, records: list[dict]) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text("".join(json.dumps(r) + "\n" for r in records), encoding="utf-8")


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="sam-synthetic-demo-") as folder:
        root = Path(folder)
        codex = root / "sources/codex/atlas.jsonl"
        claude = root / "sources/claude/demo/atlas.jsonl"
        grok = root / "sources/grok/demo/atlas/chat_history.jsonl"
        write_records(codex, [
            {"type": "session_meta", "payload": {"id": "demo-codex"}},
            {"type": "response_item", "payload": {"type": "message", "role": "user", "content": [
                {"type": "input_text", "text": "Should the fictional Atlas app use SQLite for local search?"}]}},
            {"type": "response_item", "payload": {"type": "message", "role": "assistant", "content": [
                {"type": "output_text", "text": "SQLite FTS5 fits a small offline search index with no separate server."}]}},
        ])
        write_records(claude, [
            {"type": "user", "sessionId": "demo-claude", "message": {"role": "user", "content": "What should we test before choosing SQLite?"}},
            {"type": "assistant", "sessionId": "demo-claude", "message": {"role": "assistant", "content": [
                {"type": "text", "text": "Test SQLite phrase search, Unicode inputs and repeat imports using fabricated records."}]}},
        ])
        write_records(grok, [
            {"type": "user", "content": "How can Atlas explain its SQLite decision to another assistant?"},
            {"type": "assistant", "content": [{"type": "text", "text": "Keep SQLite decision evidence with source citations; a recorded answer is not proof."}]},
        ])
        sources = [codex, claude, grok]
        before = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
        env = os.environ.copy()
        env.update({
            "SAM_CODEX_ROOT": str(root / "sources/codex"),
            "SAM_CLAUDE_ROOT": str(root / "sources/claude"),
            "SAM_GROK_ROOT": str(root / "sources/grok"),
            "SAM_PRIVATE_DIR": str(root / "runtime"),
            "SAM_MEMORY_ROOT": str(root / "curated"),
            "SAM_ARCHIVE_ROOT": str(root / "raw-archive"),
        })

        def run(*args: str) -> str:
            return subprocess.run([sys.executable, str(ROOT / "sam"), *args], env=env,
                                  capture_output=True, text=True, check=True).stdout

        print("Sovereign AI Memory | synthetic end-to-end demo")
        print("\n$ sam ingest")
        print(run("ingest"), end="")
        results = json.loads(run("search", "SQLite", "--json"))
        assert len(results) == 6, "Expected all six fabricated messages"
        assert {r["vendor"] for r in results} == {"codex", "claude", "grok"}
        print("\n$ sam search SQLite --json")
        print(f"{len(results)} cited messages across Codex, Claude Code and Grok CLI.")
        for item in sorted(results, key=lambda r: (r["vendor"], r["role"])):
            print(f"[{item['vendor']}:{item['session_id']}:{item['id']}] {item['role']}")
            print(item["text"])
        pack = run("context", "SQLite", "--max-chars", "3500")
        assert len(pack) <= 3500
        assert "Trust Boundary" in pack and "demo-codex" in pack
        output = root / "context.md"
        run("context", "SQLite", "--output", str(output))
        assert output.is_file()
        if os.name == "posix":
            assert output.stat().st_mode & 0o777 == 0o600
        assert not (root / "raw-archive").exists()
        assert before == {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
        print("\n$ sam context SQLite --output context.md")
        print("Verified: cited context, private output permissions, unchanged sources, no raw copies.")
    print("Temporary synthetic data removed. No real history was read.")


if __name__ == "__main__":
    main()
