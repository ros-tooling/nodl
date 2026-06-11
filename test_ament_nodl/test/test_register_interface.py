# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Integration tests for the ament_nodl_register_interface CMake macro.

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
    # No PACKAGE arg means the macro defaults to ${PROJECT_NAME}, so the key is test_ament_nodl__tf_listener.
    content, prefix = get_resource('nodl_interfaces', 'test_ament_nodl__tf_listener')
    assert prefix
    assert 'tf2 listener' in content


def test_explicit_package_override():
    # PACKAGE custom_pkg makes the key custom_pkg__extra_telemetry, matching what nodl://custom_pkg/extra_telemetry
    # would resolve to.
    content, _ = get_resource('nodl_interfaces', 'custom_pkg__extra_telemetry')
    assert 'explicit PACKAGE override' in content


def test_resource_content_matches_source():
    # The registered resource should be byte-identical to the source file.
    content, _ = get_resource('nodl_interfaces', 'test_ament_nodl__tf_listener')
    on_disk = (_share() / 'nodl' / 'documents' / 'tf_listener.nodl.yaml').read_text()
    assert content == on_disk


# ---------------------------------------------------------------------------
# Source file installation
# ---------------------------------------------------------------------------


def test_source_file_installed_under_registering_package():
    # Default PACKAGE installs the source under share/test_ament_nodl/nodl/interfaces/.
    assert (_share() / 'nodl' / 'documents' / 'tf_listener.nodl.yaml').is_file()


def test_source_file_installed_under_override_package():
    # PACKAGE override redirects the source-file install to share/<override>/nodl/interfaces/.
    assert (_share('custom_pkg') / 'nodl' / 'documents' / 'extra_telemetry.nodl.yaml').is_file()
