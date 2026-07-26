# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Session-scoped fixtures for nodl_schema integration tests."""

from __future__ import annotations

from pathlib import Path

import pytest

# Workspace root: ws/src/nodl/nodl_schema/test/ -> ws/
_WS_ROOT = Path(__file__).resolve().parents[4]


@pytest.fixture(scope='session')
def test_ws_path() -> Path:
    """Point pytest-colcon-ws at the embedded test workspace."""
    return Path(__file__).parent / 'test_ws'


@pytest.fixture(scope='session')
def test_ws_underlays() -> list[Path]:
    """Source the outer workspace so ament_nodl is available at build time."""
    return [_WS_ROOT / 'install' / 'setup.bash']
