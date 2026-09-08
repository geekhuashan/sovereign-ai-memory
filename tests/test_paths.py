from pathlib import Path
import os
import unittest
from unittest.mock import patch
from sovereign_memory import paths


class RuntimePathsTests(unittest.TestCase):
    def test_defaults_are_per_user(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(Path, 'home', return_value=Path('/synthetic/home')):
            self.assertEqual(paths.private_dir(), Path('/synthetic/home/.local/share/sovereign-ai-memory'))
            self.assertEqual(paths.memory_root(), paths.private_dir() / 'memory')

    def test_environment_overrides(self):
        values = {'SAM_PRIVATE_DIR': '/synthetic/private', 'SAM_MEMORY_ROOT': '/synthetic/memory',
                  'SAM_CODEX_ROOT': '/synthetic/codex', 'SAM_CLAUDE_ROOT': '/synthetic/claude',
                  'SAM_GROK_ROOT': '/synthetic/grok'}
        with patch.dict(os.environ, values):
            self.assertEqual(paths.private_dir(), Path(values['SAM_PRIVATE_DIR']))
            self.assertEqual(paths.memory_root(), Path(values['SAM_MEMORY_ROOT']))
            for vendor, root in paths.source_roots().items():
                self.assertEqual(root, Path(values[f'SAM_{vendor.upper()}_ROOT']))

    def test_xdg_absolute_path_and_private_override(self):
        with patch.dict(os.environ, {'XDG_DATA_HOME': '/synthetic/data'}, clear=True):
            self.assertEqual(paths.private_dir(), Path('/synthetic/data/sovereign-ai-memory'))
            with patch.dict(os.environ, {'SAM_PRIVATE_DIR': '/synthetic/override'}):
                self.assertEqual(paths.private_dir(), Path('/synthetic/override'))

    def test_relative_or_empty_xdg_is_ignored(self):
        for xdg in ('relative/data', '', '~/data'):
            with self.subTest(xdg=xdg), patch.dict(os.environ, {'XDG_DATA_HOME': xdg}, clear=True), patch.object(Path, 'home', return_value=Path('/synthetic/home')):
                self.assertEqual(paths.private_dir(), Path('/synthetic/home/.local/share/sovereign-ai-memory'))
