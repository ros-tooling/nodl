#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Check package versions and release-please coverage without importing setup.py."""

import argparse
import ast
import json
import os
import xml.etree.ElementTree as ET
from pathlib import Path


def check_versions(root: Path) -> list[str]:
    """Return errors for version drift or files omitted from release updates."""
    expected = json.loads((root / '.release-please-manifest.json').read_text())['.']
    config = json.loads((root / 'release-please-config.json').read_text())['packages']['.']
    covered = set(config['extra-files'])
    errors = []
    manifests = []
    for directory, children, files in os.walk(root):
        # Ignore local environments and colcon output, which are not source packages.
        children[:] = [
            name for name in children if not name.startswith('.') and name not in {'build', 'install', 'log'}
        ]
        if 'package.xml' in files:
            manifests.append(Path(directory) / 'package.xml')
    for manifest in manifests:
        relative = manifest.relative_to(root).as_posix()
        version = ET.parse(manifest).getroot().findtext('version')
        if version != expected:
            errors.append(f'{relative}: expected {expected}, got {version}')
        if relative not in covered:
            errors.append(f'{relative}: missing from extra-files')
        setup = manifest.with_name('setup.py')
        if not setup.exists():
            continue
        relative = setup.relative_to(root).as_posix()
        calls = [
            node
            for node in ast.walk(ast.parse(setup.read_text()))
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'setup'
        ]
        versions = [keyword.value for call in calls for keyword in call.keywords if keyword.arg == 'version']
        if len(versions) != 1 or not isinstance(versions[0], ast.Constant) or versions[0].value != expected:
            errors.append(f'{relative}: expected literal setup version {expected}')
        if relative not in covered:
            errors.append(f'{relative}: missing from extra-files')
        if not versions or 'x-release-please-version' not in setup.read_text().splitlines()[versions[0].lineno - 1]:
            errors.append(f'{relative}: missing release-please annotation')
    if not manifests:
        errors.append('No package.xml files found')
    for relative in sorted(covered):
        if not (root / relative).is_file():
            errors.append(f'{relative}: configured file does not exist')
    return errors


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path, help='Repository root')
    errors = check_versions(parser.parse_args().root)
    for error in errors:
        print(error)
    raise SystemExit(bool(errors))
