import contextlib
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sovereign_memory.adapters import ADAPTERS
from sovereign_memory.cli import main
from sovereign_memory.models import file_sha256
from sovereign_memory.archive import archive_raw_file
from sovereign_memory.store import MemoryStore


def record(vendor, text):
    if vendor == 'codex':
        value = {'type': 'response_item', 'payload': {'type': 'message', 'role': 'user', 'content': [{'type': 'input_text', 'text': text}]}}
    elif vendor == 'claude':
        value = {'type': 'user', 'message': {'role': 'user', 'content': text}}
    else:
        value = {'type': 'user', 'content': text}
    return (json.dumps(value) + '\n').encode()


class SourceSnapshotTests(unittest.TestCase):
    def test_append_after_capture_keeps_text_and_hash_consistent(self):
        for vendor, adapter in ADAPTERS.items():
            with self.subTest(vendor=vendor), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                source = root / 'session.jsonl'
                initial = record(vendor, 'captured')
                source.write_bytes(initial)
                original_read = Path.read_bytes
                def read_then_append(path):
                    data = original_read(path)
                    if path == source:
                        with path.open('ab') as handle:
                            handle.write(record(vendor, 'later'))
                    return data
                with patch.object(Path, 'read_bytes', read_then_append):
                    session = adapter.parse(source, root)
                self.assertEqual([message.text for message in session.messages], ['captured'])
                self.assertEqual(session.source_sha256, hashlib.sha256(initial).hexdigest())
                self.assertTrue(all(message.source_sha256 == session.source_sha256 for message in session.messages))
                self.assertNotEqual(session.source_sha256, file_sha256(source))

    def test_raw_ingest_refuses_source_changed_after_parse(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_root = root / 'sources'
            source_root.mkdir()
            source = source_root / 'session.jsonl'
            source.write_bytes(record('codex', 'captured'))
            adapter = ADAPTERS['codex']
            original_parse = adapter.parse
            def parse_then_append(path, source_root):
                session = original_parse(path, source_root)
                with path.open('ab') as handle:
                    handle.write(record('codex', 'later'))
                return session
            with patch.object(adapter, 'parse', parse_then_append), patch('sovereign_memory.cli.source_roots', return_value={'codex': source_root}), patch('sovereign_memory.cli.private_dir', return_value=root / 'private'), contextlib.redirect_stdout(io.StringIO()) as output, contextlib.redirect_stderr(io.StringIO()):
                result = main(['ingest', '--vendor', 'codex', '--archive-raw', '--raw-root', str(root / 'raw')])
            self.assertEqual(result, 1)
            self.assertIn('archived=0', output.getvalue())
            self.assertFalse((root / 'raw').exists())
            self.assertEqual(MemoryStore(root / 'private').counts()['messages'], 0)

    def test_mismatch_preserves_existing_archive(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'session.jsonl'
            source.write_text('old')
            destination, digest, _ = archive_raw_file(source, root, root / 'raw', 'codex')
            source.write_text('new')
            with self.assertRaises(ValueError):
                archive_raw_file(source, root, root / 'raw', 'codex', expected_sha256=digest)
            self.assertEqual(destination.read_text(), 'old')
