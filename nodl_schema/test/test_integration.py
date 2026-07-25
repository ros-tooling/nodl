# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Integration tests for NoDL include resolution via the ament index.

These tests require the embedded test workspace to be built (handled
automatically by the ``test_ws_env`` session fixture in conftest.py).
"""

from __future__ import annotations

from pathlib import Path


def test_test_ws_env_has_test_packages(test_ws_env):
    """Smoke test: the test workspace env includes our fragment packages."""
    ament_prefix_path = test_ws_env.get('AMENT_PREFIX_PATH', '')
    assert 'nodl_fragment_a' in ament_prefix_path
    assert 'nodl_fragment_b' in ament_prefix_path


def test_nodl_files_installed(test_ws_env):
    """Smoke test: NoDL files are actually installed in the test workspace."""
    ament_prefix_path = test_ws_env['AMENT_PREFIX_PATH']
    prefixes = ament_prefix_path.split(':')

    # Find the nodl_fragment_a prefix
    frag_a_prefix = next((p for p in prefixes if 'nodl_fragment_a' in p), None)
    assert frag_a_prefix is not None, f'nodl_fragment_a not in AMENT_PREFIX_PATH: {ament_prefix_path}'

    nodl_dir = Path(frag_a_prefix) / 'share' / 'nodl_fragment_a' / 'nodl'
    assert nodl_dir.is_dir(), f'NoDL directory not found: {nodl_dir}'
    assert (nodl_dir / 'diagnostics.nodl.yaml').is_file()
    assert (nodl_dir / 'shared_base.nodl.yaml').is_file()
