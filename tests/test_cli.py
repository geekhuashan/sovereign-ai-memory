from __future__ import annotations

from pathlib import Path
import tempfile
import io
import os
import contextlib
import unittest
from unittest import mock

from sovereign_memory.cli import build_parser, main


def _write_codex_session(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    session = root / "session.jsonl"
    session.write_text(
        '{"type":"response_item","payload":{"type":"message","role":"user",'
        '"content":[{"type":"input_text","text":"hello"}]}}\n', encoding="utf-8")



class IngestArchiveDefaultTests(unittest.TestCase):
    def _run_ingest(self, extra_args: list[str], private_dir: Path, source_root: Path) -> None:
        parser = build_parser()
        args = parser.parse_args(["ingest", "--vendor", "codex", *extra_args])
        with mock.patch(
            "sovereign_memory.cli.source_roots",
            return_value={"codex": source_root, "claude": source_root, "grok": source_root},
        ), mock.patch("sovereign_memory.cli.private_dir", return_value=private_dir):
            args.func(args)

    def test_ingest_archives_only_with_opt_in(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_root = root / "source"
            _write_codex_session(source_root)
            private_dir = root / "private"
            archive_root = private_dir / "raw-archive"

            with mock.patch("sovereign_memory.cli.archive_root", return_value=archive_root):
                self._run_ingest(["--archive-raw"], private_dir, source_root)

            archived = list(archive_root.rglob("*.jsonl"))
            self.assertEqual(len(archived), 1)

    def test_no_archive_raw_skips_archival(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_root = root / "source"
            _write_codex_session(source_root)
            private_dir = root / "private"
            archive_root = private_dir / "raw-archive"

            with mock.patch("sovereign_memory.cli.archive_root", return_value=archive_root):
                self._run_ingest(["--no-archive-raw"], private_dir, source_root)

            self.assertFalse(archive_root.exists())

    def test_default_does_not_archive_and_preserves_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            _write_codex_session(source)
            before = (source / "session.jsonl").read_bytes()
            with mock.patch("sovereign_memory.cli.archive_root", return_value=root / "raw"):
                self._run_ingest([], root / "private", source)
            self.assertFalse((root / "raw").exists())
            self.assertEqual((source / "session.jsonl").read_bytes(), before)
            from sovereign_memory.store import MemoryStore
            self.assertEqual(MemoryStore(root / "private").counts()["messages"], 1)

    def test_invalid_limits_and_empty_query_rejected(self):
        for argv in (["ingest", "--limit", "0"], ["search", "x", "--limit", "-1"],
                     ["context", "x", "--max-chars", "0"], ["search", " "]):
            with self.subTest(argv=argv), contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as raised:
                build_parser().parse_args(argv)
            self.assertEqual(raised.exception.code, 2)

    def test_context_output_replaces_symlink_with_private_file(self):
        if os.name == "nt":
            self.skipTest("POSIX permissions and symlinks")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "original"
            target.write_text("preserve")
            output = root / "context.md"
            output.symlink_to(target)
            with mock.patch("sovereign_memory.cli.private_dir", return_value=root / "private"), mock.patch("sovereign_memory.cli.memory_root", return_value=root / "memory"):
                self.assertEqual(main(["context", "hello", "--output", str(output)]), 0)
            self.assertEqual(target.read_text(), "preserve")
            self.assertFalse(output.is_symlink())
            self.assertEqual(output.stat().st_mode & 0o777, 0o600)

    def test_doctor_missing_optional_sources_is_success(self):
        with mock.patch("sovereign_memory.cli.source_roots", return_value={"codex": Path('/nonexistent-synthetic-source')}), mock.patch("sovereign_memory.cli.sys.platform", "linux"), contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(["doctor"]), 0)
        self.assertIn("not checked on this platform", output.getvalue())



if __name__ == "__main__":
    unittest.main()
