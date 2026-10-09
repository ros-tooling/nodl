# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0

"""Check which generated C++ fixtures are installed and exported.

The checks read the install manifests written by the build that is being tested.
Files that earlier builds left in the install prefix are therefore ignored.
A regular install records every file in ``install_manifest.txt``.
A ``--symlink-install`` records its symlinked files in ``symlink_install_manifest.txt`` and only the libraries in ``install_manifest.txt``.
"""

import fnmatch
import os
from pathlib import Path

import pytest
from ament_index_python.packages import get_package_prefix

PACKAGE = 'test_nodl_generators'
PREFIX = Path(get_package_prefix(PACKAGE))
BUILD_DIR = Path(os.environ['BUILD_DIR'])
MANIFESTS = [BUILD_DIR / 'install_manifest.txt', BUILD_DIR / 'symlink_install_manifest.txt']
# Installed files relative to the install prefix, for example ``lib/libtest_nodl_generators_x.so``.
INSTALLED = sorted(
    Path(line).relative_to(PREFIX).as_posix()
    for manifest in MANIFESTS
    if manifest.exists()
    for line in manifest.read_text().splitlines()
)
HEADER_DIR = f'include/{PACKAGE}/{PACKAGE}'
CMAKE_DIR = f'share/{PACKAGE}/cmake'


def _installed(pattern: str) -> list[str]:
    """Return the installed files that match a glob pattern relative to the install prefix."""
    return fnmatch.filter(INSTALLED, pattern)


def _library(target: str) -> list[str]:
    return _installed(f'lib/lib{PACKAGE}_{target}.*')


def _headers(target: str) -> list[str]:
    return _installed(f'{HEADER_DIR}/{target}*')


def _export_files(target: str) -> list[str]:
    return _installed(f'{CMAKE_DIR}/export_{target}Export*.cmake')


@pytest.mark.parametrize(
    'target',
    [
        'cpp_minimal_node_base',
        'cpp_pub_sub_node_base',
        'cpp_services_node_base',
        'cpp_lifecycle_node_base',
        'cpp_params_node_base',
    ],
)
def test_default_fixture_is_exported(target):
    assert f'{HEADER_DIR}/{target}.hpp' in INSTALLED
    assert _export_files(target)
    assert _library(target)


def test_parameter_header_is_installed():
    assert f'{HEADER_DIR}/cpp_params_node_base_parameters.hpp' in INSTALLED


@pytest.mark.parametrize(
    'target',
    ['cpp_minimal_node_base', 'cpp_params_node_base'],
)
def test_only_headers_are_installed(target):
    installed = {Path(f).name for f in _headers(target)}

    assert installed <= {f'{target}.hpp', f'{target}_parameters.hpp'}


def test_no_export_fixture_installs_only_the_library():
    target = 'cpp_kitchen_sink_node_base'

    assert _library(target)
    assert not _headers(target)
    assert not _export_files(target)


def test_static_fixture_is_not_installed():
    target = 'cpp_minimal_static_node_base'

    assert not _library(target)
    assert not _headers(target)
    assert not _export_files(target)
