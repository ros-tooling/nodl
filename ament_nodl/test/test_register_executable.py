# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Integration tests for the ament_nodl_register_executable CMake macro.

The jig package registers ``sensor_driver`` via
``ament_nodl_register_executable``.  We verify the resource entry and
the installed NoDL file.
"""

from __future__ import annotations

from pathlib import Path

from pytest_colcon_ws import read_resource


def _share_dir(env: dict[str, str], pkg: str = 'test_ament_nodl') -> Path:
    """Resolve the share directory for a package from AMENT_PREFIX_PATH."""
    for prefix in env['AMENT_PREFIX_PATH'].split(':'):
        share = Path(prefix) / 'share' / pkg
        if share.is_dir():
            return share
    raise FileNotFoundError(f'share directory for {pkg!r} not found')


# ---------------------------------------------------------------------------
# Resource registration (nodl_executables)
# ---------------------------------------------------------------------------


def test_executable_resource_registered(test_ws_env):
    """ament_nodl_register_executable creates a nodl_executables resource."""
    content = read_resource(test_ws_env, 'nodl_executables', 'test_ament_nodl')
    assert 'sensor_driver' in content
    assert 'sensor_driver.nodl.yaml' in content


def test_executable_resource_format(test_ws_env):
    """The resource content follows the <exe>:<nodl_path> format."""
    content = read_resource(test_ws_env, 'nodl_executables', 'test_ament_nodl')
    lines = [line for line in content.strip().splitlines() if line]
    assert any(line == 'sensor_driver:nodl/sensor_driver.nodl.yaml' for line in lines), (
        f'Unexpected resource content:\n{content}'
    )


# ---------------------------------------------------------------------------
# File installation (via the internal ament_nodl_install call)
# ---------------------------------------------------------------------------


def test_executable_nodl_file_installed(test_ws_env):
    """The NoDL file is installed under share/<pkg>/nodl/ by the macro."""
    share = _share_dir(test_ws_env)
    assert (share / 'nodl' / 'sensor_driver.nodl.yaml').is_file()


def test_executable_also_in_nodl_interfaces(test_ws_env):
    """ament_nodl_register_executable also registers the file via ament_nodl_install."""
    content = read_resource(test_ws_env, 'nodl_interfaces', 'test_ament_nodl')
    assert 'sensor_driver.nodl.yaml' in content
