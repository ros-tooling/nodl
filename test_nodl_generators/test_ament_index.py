# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0

"""Check which generated C++ fixtures are registered with the ament index.

The checks read the install manifests written by the build that is being tested.
Files that earlier builds left in the install prefix are therefore ignored.
A regular install records every file in ``install_manifest.txt``.
A ``--symlink-install`` records its symlinked files in ``symlink_install_manifest.txt`` and only the libraries in ``install_manifest.txt``.
"""

import os
from pathlib import Path

from ament_index_python.packages import get_package_prefix

PACKAGE = 'test_nodl_generators'
PREFIX = Path(get_package_prefix(PACKAGE))
BUILD_DIR = Path(os.environ['BUILD_DIR'])
MANIFESTS = [BUILD_DIR / 'install_manifest.txt', BUILD_DIR / 'symlink_install_manifest.txt']
INDEX_DIR = PREFIX / 'share/ament_index/resource_index/nodl'


def _registered_resources() -> set[str]:
    installed = (
        Path(line) for manifest in MANIFESTS if manifest.exists() for line in manifest.read_text().splitlines()
    )
    return {path.name.removeprefix(f'{PACKAGE}__') for path in installed if path.parent == INDEX_DIR}


def test_fixtures_are_registered_under_their_target_names_or_overrides():
    assert _registered_resources() == {
        'cpp_minimal_node_base',
        'cpp_pub_sub_node',
        'cpp_services_node_base',
        'cpp_params_node_base',
        'cpp_kitchen_sink_node_base',
        'cpp_lifecycle_node_base',
        'cpp_namespace_node',
    }


def test_no_index_fixture_is_not_registered():
    assert not [name for name in _registered_resources() if 'static' in name]


def test_registered_document_keeps_its_endpoints_and_includes():
    registered = (INDEX_DIR / f'{PACKAGE}__cpp_pub_sub_node').read_text()

    assert 'nodl://nodl_common_interfaces/node' in registered
    assert 'name: status' in registered
    assert 'name: cmd_vel' in registered
