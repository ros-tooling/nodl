# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Session-scoped fixtures for ament_nodl integration tests."""

from __future__ import annotations

import os
from pathlib import Path

import pytest


def _find_underlay_setup() -> Path:
    """Resolve the outer workspace setup.bash from the environment.

    When running under ``colcon test`` or from a sourced workspace the
    ``AMENT_PREFIX_PATH`` environment variable contains the install
    prefixes that provide ``ament_nodl`` and its dependencies.  We walk
    up from the first prefix that contains ``ament_nodl`` to find the
    workspace-level ``setup.bash``.
    """
    ament_prefix_path = os.environ.get('AMENT_PREFIX_PATH', '')
    for prefix in ament_prefix_path.split(':'):
        if not prefix:
            continue
        marker = Path(prefix) / 'share' / 'ament_index' / 'resource_index' / 'packages' / 'ament_nodl'
        if marker.is_file():
            # prefix is e.g. <ws>/install/ament_nodl  →  <ws>/install/setup.bash
            setup = Path(prefix).parent / 'setup.bash'
            if setup.is_file():
                return setup
    pytest.fail(
        'Could not locate the outer workspace install containing ament_nodl. '
        'Make sure the workspace is sourced (AMENT_PREFIX_PATH must include '
        'a prefix with ament_nodl installed).'
    )


@pytest.fixture(scope='session')
def test_ws_path() -> Path:
    """Point pytest-colcon-ws at the embedded test workspace."""
    return Path(__file__).parent / 'test_ws'


@pytest.fixture(scope='session')
def test_ws_underlays() -> list[Path]:
    """Source the outer workspace so ament_nodl is available at build time."""
    return [_find_underlay_setup()]
