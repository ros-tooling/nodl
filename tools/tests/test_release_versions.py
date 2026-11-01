# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Exercise release version drift and updater coverage with temporary packages."""

import importlib.util
import json
import runpy
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

spec = importlib.util.spec_from_file_location(
    'check_release_versions', Path(__file__).parents[1] / 'check_release_versions.py'
)
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


class ReleaseVersionsTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        (self.root / '.release-please-manifest.json').write_text('{".": "2.0.3"}')
        (self.root / 'release-please-config.json').write_text(
            json.dumps({'packages': {'.': {'extra-files': ['pkg/package.xml']}}})
        )
        package = self.root / 'pkg'
        package.mkdir()
        (package / 'package.xml').write_text('<package><version>2.0.3</version></package>')

    def test_aligned_versions(self):
        self.assertEqual(checker.check_versions(self.root), [])

    def test_manifest_version_drift(self):
        (self.root / 'pkg/package.xml').write_text('<package><version>0.1.0</version></package>')
        self.assertEqual(checker.check_versions(self.root), ['pkg/package.xml: expected 2.0.3, got 0.1.0'])

    def test_new_package_missing_from_release_config(self):
        package = self.root / 'new_pkg'
        package.mkdir()
        (package / 'package.xml').write_text('<package><version>2.0.3</version></package>')
        self.assertEqual(checker.check_versions(self.root), ['new_pkg/package.xml: missing from extra-files'])

    def test_local_environments_and_build_outputs_are_ignored(self):
        for name in ('.venv', 'build', 'install', 'log'):
            directory = self.root / name
            directory.mkdir()
            (directory / 'package.xml').write_text('<package><version>1.0.0</version></package>')
        self.assertEqual(checker.check_versions(self.root), [])

    def test_missing_configured_manifest(self):
        (self.root / 'pkg/package.xml').unlink()
        self.assertEqual(
            checker.check_versions(self.root),
            [
                'No package.xml files found',
                'pkg/package.xml: configured file does not exist',
            ],
        )

    def test_setup_versions_and_pytest_metadata(self):
        root = Path(__file__).resolve().parents[2]
        scripts = sorted(root.glob('*/setup.py'))
        self.assertTrue(scripts)
        for source in scripts:
            for version in ('2.0.3', '3.1.7'):
                with self.subTest(package=source.parent.name, version=version):
                    script = self.root / 'setup.py'
                    script.write_text(source.read_text())
                    (self.root / 'package.xml').write_text(f'<package><version>{version}</version></package>')
                    setuptools = types.ModuleType('setuptools')
                    setuptools.setup = Mock()
                    setuptools.find_packages = Mock(return_value=[])
                    with patch.dict(sys.modules, {'setuptools': setuptools}):
                        runpy.run_path(str(script))
                    metadata = setuptools.setup.call_args.kwargs
                    self.assertEqual(metadata['version'], version)
                    # Missing pytest metadata makes colcon fall back to unittest.
                    self.assertIn('pytest', metadata.get('extras_require', {}).get('test', []))
