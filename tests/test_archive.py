from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import unittest

from sovereign_memory.archive import archive_raw_file


class ArchiveTests(unittest.TestCase):
    def test_archive_is_verified_read_only_and_updateable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            source_root = base / "source"
            source_root.mkdir()
            source = source_root / "session.jsonl"
            source.write_text("first\n", encoding="utf-8")
            archive_root = base / "archive"

            destination, first_hash, copied = archive_raw_file(
                source, source_root, archive_root, "codex"
            )
            self.assertTrue(copied)
            self.assertEqual(destination.read_text(encoding="utf-8"), "first\n")
            self.assertEqual(os.stat(destination).st_mode & 0o777, 0o400)

            sidecar = destination.with_name(destination.name + ".sha256.json")
            self.assertEqual(json.loads(sidecar.read_text())["digest"], first_hash)
            self.assertEqual(os.stat(sidecar).st_mode & 0o777, 0o400)

            _, repeated_hash, copied = archive_raw_file(
                source, source_root, archive_root, "codex"
            )
            self.assertFalse(copied)
            self.assertEqual(repeated_hash, first_hash)

            source.write_text("second\n", encoding="utf-8")
            destination, second_hash, copied = archive_raw_file(
                source, source_root, archive_root, "codex"
            )
            self.assertTrue(copied)
            self.assertNotEqual(second_hash, first_hash)
            self.assertEqual(destination.read_text(encoding="utf-8"), "second\n")
            self.assertEqual(json.loads(sidecar.read_text())["digest"], second_hash)


if __name__ == "__main__":
    unittest.main()
