# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Exercise release version drift and updater coverage with temporary packages."""

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

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
            json.dumps({'packages': {'.': {'extra-files': ['pkg/package.xml', 'pkg/setup.py']}}})
        )
        package = self.root / 'pkg'
        package.mkdir()
        (package / 'package.xml').write_text('<package><version>2.0.3</version></package>')
        # The checker must parse this file without executing it.
        (package / 'setup.py').write_text(
            "raise RuntimeError('do not execute')\nsetup(version='2.0.3')  # x-release-please-version\n"
        )

    def test_aligned_versions(self):
        self.assertEqual(checker.check_versions(self.root), [])

    def test_manifest_version_drift(self):
        (self.root / 'pkg/package.xml').write_text('<package><version>0.1.0</version></package>')
        self.assertEqual(checker.check_versions(self.root), ['pkg/package.xml: expected 2.0.3, got 0.1.0'])

    def test_python_version_drift(self):
        setup = self.root / 'pkg/setup.py'
        setup.write_text(setup.read_text().replace('2.0.3', '2.0.2'))
        self.assertEqual(checker.check_versions(self.root), ['pkg/setup.py: expected literal setup version 2.0.3'])

    def test_new_package_missing_from_release_config(self):
        package = self.root / 'new_pkg'
        package.mkdir()
        (package / 'package.xml').write_text('<package><version>2.0.3</version></package>')
        self.assertEqual(checker.check_versions(self.root), ['new_pkg/package.xml: missing from extra-files'])

    def test_missing_annotation(self):
        (self.root / 'pkg/setup.py').write_text("# x-release-please-version\nsetup(version='2.0.3')\n")
        self.assertEqual(checker.check_versions(self.root), ['pkg/setup.py: missing release-please annotation'])

    def test_local_environments_and_build_outputs_are_ignored(self):
        for name in ('.venv', 'build', 'install', 'log'):
            directory = self.root / name
            directory.mkdir()
            (directory / 'package.xml').write_text('<package><version>1.0.0</version></package>')
        self.assertEqual(checker.check_versions(self.root), [])
