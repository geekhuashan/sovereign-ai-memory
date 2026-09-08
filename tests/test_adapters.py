from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from sovereign_memory.adapters.claude import ClaudeAdapter
from sovereign_memory.adapters.codex import CodexAdapter
from sovereign_memory.adapters.grok import GrokAdapter


def write_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(record) + "\n" for record in records),
        encoding="utf-8",
    )


class AdapterTests(unittest.TestCase):
    def test_claude_discovery_excludes_subagent_logs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            main = root / "project" / "session.jsonl"
            subagent = root / "project" / "session" / "subagents" / "agent.jsonl"
            write_jsonl(main, [])
            write_jsonl(subagent, [])
            self.assertEqual(list(ClaudeAdapter().discover(root)), [main])

    def test_codex_extracts_user_and_assistant_text_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "session.jsonl"
            write_jsonl(
                path,
                [
                    {"type": "session_meta", "payload": {"id": "codex-1"}},
                    {
                        "timestamp": "2026-01-01T00:00:00Z",
                        "type": "response_item",
                        "payload": {
                            "type": "message",
                            "role": "user",
                            "content": [{"type": "input_text", "text": "hello"}],
                        },
                    },
                    {
                        "type": "response_item",
                        "payload": {"type": "reasoning", "summary": ["private"]},
                    },
                    {
                        "type": "response_item",
                        "payload": {
                            "type": "message",
                            "role": "assistant",
                            "content": [{"type": "output_text", "text": "world"}],
                        },
                    },
                    {"type": "response_item", "payload": {"type": "message", "role": "assistant", "channel": "analysis", "content": [{"type": "output_text", "text": "hidden analysis"}]}},
                    {"type": "session_meta", "payload": {"id": "codex-2"}},
                    {
                        "type": "response_item",
                        "payload": {
                            "type": "message",
                            "role": "user",
                            "content": [{"type": "input_text", "text": "next"}],
                        },
                    },
                ],
            )
            session = CodexAdapter().parse(path, root)
            self.assertEqual(session.session_id, "codex-1")
            self.assertEqual(
                [message.text for message in session.messages], ["hello", "world", "next"]
            )
            self.assertEqual(
                [message.session_id for message in session.messages],
                ["codex-1", "codex-1", "codex-2"],
            )

    def test_claude_excludes_thinking_and_sidechains(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "session.jsonl"
            write_jsonl(
                path,
                [
                    {
                        "type": "user",
                        "sessionId": "claude-1",
                        "message": {"role": "user", "content": "question"},
                    },
                    {
                        "type": "assistant",
                        "sessionId": "claude-1",
                        "message": {
                            "role": "assistant",
                            "content": [
                                {"type": "thinking", "thinking": "hidden"},
                                {"type": "text", "text": "answer"},
                            ],
                        },
                    },
                    {
                        "type": "assistant",
                        "sessionId": "claude-1",
                        "isSidechain": True,
                        "message": {"role": "assistant", "content": "sidechain"},
                    },
                    {"type": "user", "message": {"role": "tool", "content": "tool output"}},
                    {"type": "user", "message": {"role": "system", "content": "system text"}},
                ],
            )
            session = ClaudeAdapter().parse(path, root)
            self.assertEqual([message.text for message in session.messages], ["question", "answer"])

    def test_grok_excludes_system_reasoning_and_tools(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "%2Fworkspace" / "grok-1" / "chat_history.jsonl"
            write_jsonl(
                path,
                [
                    {"type": "system", "content": "system"},
                    {"type": "user", "content": "ask"},
                    {"type": "reasoning", "content": "hidden"},
                    {
                        "type": "assistant",
                        "content": [{"type": "text", "text": "reply"}],
                    },
                    {"type": "tool_result", "content": "secret output"},
                ],
            )
            session = GrokAdapter().parse(path, root)
            self.assertEqual(session.session_id, "grok-1")
            self.assertEqual([message.text for message in session.messages], ["ask", "reply"])


if __name__ == "__main__":
    unittest.main()
