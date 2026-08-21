# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Integration tests for the ament_nodl_register CMake macro.

The macro is exercised at configure / install time by this package's
CMakeLists.txt; here we assert on the resulting ament index and install
tree without re-invoking CMake.
"""

from pathlib import Path

from ament_index_python.packages import PackageNotFoundError, get_package_share_directory
from ament_index_python.resources import get_resource


def _share(pkg: str = 'test_ament_nodl') -> Path:
    # Real packages resolve through the ament index.
    # Virtual packages used only as a PACKAGE override aren't registered, so we
    # resolve them as siblings under the registering package's install prefix.
    try:
        return Path(get_package_share_directory(pkg))
    except PackageNotFoundError:
        return Path(get_package_share_directory('test_ament_nodl')).parent / pkg


# ---------------------------------------------------------------------------
# Resource registration
# ---------------------------------------------------------------------------


def test_default_package_uses_project_name():
    # No PACKAGE arg means the macro defaults to ${PROJECT_NAME}, so the key is test_ament_nodl__basic_node.
    content, prefix = get_resource('nodl', 'test_ament_nodl__basic_node')
    assert prefix
    assert 'Basic test node' in content


def test_explicit_package_override():
    # PACKAGE custom_pkg makes the key custom_pkg__custom_exe even though the registering package is test_ament_nodl.
    content, _ = get_resource('nodl', 'custom_pkg__custom_exe')
    assert 'explicit PACKAGE override' in content


def test_json_frontend_is_installed_as_yaml():
    # A .nodl.json source is accepted, but the installed resource is uniformly YAML.
    content, _ = get_resource('nodl', 'test_ament_nodl__json_node')
    assert '"nodl_version": 2' not in content
    assert 'nodl_version: 2' in content


def test_index_and_share_copies_match():
    # The ament index resource and the share/ copy are the same installed (rewritten) document.
    content, _ = get_resource('nodl', 'test_ament_nodl__basic_node')
    on_disk = (_share() / 'nodl' / 'basic_node.nodl.yaml').read_text()
    assert content == on_disk


# ---------------------------------------------------------------------------
# Source file installation
# ---------------------------------------------------------------------------


def test_source_file_installed_under_registering_package():
    # Default PACKAGE installs the source under share/test_ament_nodl/nodl/.
    assert (_share() / 'nodl' / 'basic_node.nodl.yaml').is_file()


def test_json_source_file_installed_as_yaml():
    # The source stem is kept, but the installed copy is uniformly YAML.
    assert (_share() / 'nodl' / 'json_node.nodl.yaml').is_file()
    assert not (_share() / 'nodl' / 'json_node.nodl.json').is_file()


def test_source_file_installed_under_override_package():
    # PACKAGE override redirects the source-file install to share/<override>/nodl/.
    target = _share('custom_pkg') / 'nodl' / 'alt_pkg_node.nodl.yaml'
    assert target.is_file()
