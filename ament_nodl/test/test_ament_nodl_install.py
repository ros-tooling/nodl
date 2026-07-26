# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Integration tests for the ament_nodl_install CMake macro.

The macro is exercised at configure / install time by the test_ament_nodl
jig package; here we assert on the resulting ament index and install tree.
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
# Resource registration (nodl_interfaces)
# ---------------------------------------------------------------------------


def test_nodl_interfaces_resource_registered(test_ws_env):
    """ament_nodl_install registers filenames under the nodl_interfaces resource."""
    content = read_resource(test_ws_env, 'nodl_interfaces', 'test_ament_nodl')
    assert 'base_interfaces.nodl.yaml' in content
    assert 'diagnostics.nodl.yaml' in content


def test_json_file_in_nodl_interfaces_resource(test_ws_env):
    """Non-YAML files are also registered under nodl_interfaces."""
    content = read_resource(test_ws_env, 'nodl_interfaces', 'test_ament_nodl')
    assert 'json_node.nodl.json' in content


# ---------------------------------------------------------------------------
# File installation
# ---------------------------------------------------------------------------


def test_yaml_files_installed(test_ws_env):
    """NoDL YAML files are installed under share/<pkg>/nodl/."""
    share = _share_dir(test_ws_env)
    assert (share / 'nodl' / 'base_interfaces.nodl.yaml').is_file()
    assert (share / 'nodl' / 'diagnostics.nodl.yaml').is_file()


def test_json_file_installed(test_ws_env):
    """Non-YAML NoDL files preserve their original extension."""
    share = _share_dir(test_ws_env)
    assert (share / 'nodl' / 'json_node.nodl.json').is_file()


def test_installed_content_matches_source(test_ws_env, test_ws_path):
    """Installed files are byte-identical to the source files."""
    share = _share_dir(test_ws_env)
    installed = (share / 'nodl' / 'base_interfaces.nodl.yaml').read_text()
    source = (test_ws_path / 'src' / 'test_ament_nodl' / 'nodl' / 'base_interfaces.nodl.yaml').read_text()
    assert installed == source
