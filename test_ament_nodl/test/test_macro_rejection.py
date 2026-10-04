# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""End-to-end test that the ament_nodl_register macro propagates validator failures as build failures.

Writes a tiny inner ament_cmake project that registers an intentionally-invalid NoDL file via the macro,
then spawns cmake to configure and build it; the build is expected to fail with the validator error.
This catches regressions in the macro wiring itself, separate from the CLI tests in nodl_schema that
already cover the validator's behavior in isolation.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest

_INNER_CMAKELISTS = textwrap.dedent("""
    cmake_minimum_required(VERSION 3.22)
    project(rejection_fixture)
    find_package(ament_cmake REQUIRED)
    find_package(ament_nodl REQUIRED)
    ament_nodl_register(bad_exe FILE bad.nodl.yaml)
    ament_package()
""")

_INNER_PACKAGE_XML = textwrap.dedent("""<?xml version="1.0"?>
    <package format="3">
      <name>rejection_fixture</name>
      <version>0.0.0</version>
      <description>Inner project used by test_ament_nodl to verify the macro rejects invalid files.</description>
      <maintainer email="test@example.com">test</maintainer>
      <license>Apache-2.0</license>
      <buildtool_depend>ament_cmake</buildtool_depend>
      <buildtool_depend>ament_nodl</buildtool_depend>
      <export>
        <build_type>ament_cmake</build_type>
      </export>
    </package>
""").lstrip()

_INVALID_NODL = textwrap.dedent("""
    nodl_version: 2
    parameters:
      bad:
        type: not_a_real_type
""").lstrip()

# A project that registers a document whose local:// include points at an unregistered sibling.
# The sibling exists on disk (so validation resolves it) but is never registered, so the rewrite
# has no nodl:// key to substitute and must fail configuration.
_UNREGISTERED_INCLUDE_CMAKELISTS = textwrap.dedent("""
    cmake_minimum_required(VERSION 3.22)
    project(unregistered_include_fixture)
    find_package(ament_cmake REQUIRED)
    find_package(ament_nodl REQUIRED)
    ament_nodl_register(root_exe FILE root.nodl.yaml)
    ament_package()
""")

_UNREGISTERED_INCLUDE_PACKAGE_XML = textwrap.dedent("""<?xml version="1.0"?>
    <package format="3">
      <name>unregistered_include_fixture</name>
      <version>0.0.0</version>
      <description>Inner project verifying the macro rejects an unregistered local include target.</description>
      <maintainer email="test@example.com">test</maintainer>
      <license>Apache-2.0</license>
      <buildtool_depend>ament_cmake</buildtool_depend>
      <buildtool_depend>ament_nodl</buildtool_depend>
      <export>
        <build_type>ament_cmake</build_type>
      </export>
    </package>
""").lstrip()

_ROOT_WITH_LOCAL_INCLUDE = textwrap.dedent("""
    nodl_version: 2
    include:
      - ref: local://leaf.nodl.yaml
""").lstrip()

_LEAF_NODL = 'nodl_version: 2\n'


@pytest.fixture
def inner_pkg(tmp_path: Path) -> Path:
    pkg = tmp_path / 'rejection_fixture'
    pkg.mkdir()
    (pkg / 'CMakeLists.txt').write_text(_INNER_CMAKELISTS)
    (pkg / 'package.xml').write_text(_INNER_PACKAGE_XML)
    (pkg / 'bad.nodl.yaml').write_text(_INVALID_NODL)
    return pkg


@pytest.mark.skipif(shutil.which('cmake') is None, reason='cmake not on PATH')
def test_macro_rejects_invalid_node(inner_pkg: Path):
    # Inherit AMENT_PREFIX_PATH from the colcon-test env so the inner build
    # can resolve find_package(ament_nodl) and find python with nodl_schema.
    build = inner_pkg / 'build'
    configure = subprocess.run(
        ['cmake', '-S', str(inner_pkg), '-B', str(build)],
        capture_output=True,
        text=True,
        env=os.environ,
    )
    assert configure.returncode == 0, f'Configure failed:\n{configure.stderr}'

    result = subprocess.run(
        ['cmake', '--build', str(build)],
        capture_output=True,
        text=True,
        env=os.environ,
    )
    assert result.returncode != 0, 'Expected the inner build to fail on the invalid NoDL file'
    combined = result.stdout + result.stderr
    assert 'not_a_real_type' in combined, (
        f'Expected the validator error to appear in the build output, got:\n{combined}'
    )


def _unwrapped(*outputs: str) -> str:
    # CMake wraps long error messages, so compare on single-spaced text.
    return ' '.join(' '.join(outputs).split())


def _configure(pkg: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ['cmake', '-S', str(pkg), '-B', str(pkg / 'build')],
        capture_output=True,
        text=True,
        env=os.environ,
    )


@pytest.fixture
def unregistered_include_pkg(tmp_path: Path) -> Path:
    pkg = tmp_path / 'unregistered_include_fixture'
    pkg.mkdir()
    (pkg / 'CMakeLists.txt').write_text(_UNREGISTERED_INCLUDE_CMAKELISTS)
    (pkg / 'package.xml').write_text(_UNREGISTERED_INCLUDE_PACKAGE_XML)
    (pkg / 'root.nodl.yaml').write_text(_ROOT_WITH_LOCAL_INCLUDE)
    (pkg / 'leaf.nodl.yaml').write_text(_LEAF_NODL)
    return pkg


@pytest.mark.skipif(shutil.which('cmake') is None, reason='cmake not on PATH')
def test_macro_rejects_unregistered_local_include(unregistered_include_pkg: Path):
    configure = _configure(unregistered_include_pkg)

    assert configure.returncode != 0
    message = _unwrapped(configure.stderr)
    assert 'unregistered_include_fixture__root_exe includes a local:// reference that is not registered' in message
    assert 'local reference local://leaf.nodl.yaml was not registered to rewrite' in message
    assert 'Register the included file with ament_nodl_register(<name> FILE <path>) in the same package' in message


@pytest.mark.skipif(shutil.which('cmake') is None, reason='cmake not on PATH')
def test_macro_rechecks_includes_when_a_registered_document_changes(unregistered_include_pkg: Path):
    # Configured while the root document has no includes, then edited to include the unregistered sibling.
    root = unregistered_include_pkg / 'root.nodl.yaml'
    root.write_text(_LEAF_NODL)
    assert _configure(unregistered_include_pkg).returncode == 0

    root.write_text(_ROOT_WITH_LOCAL_INCLUDE)
    build = subprocess.run(
        ['cmake', '--build', str(unregistered_include_pkg / 'build')],
        capture_output=True,
        text=True,
        env=os.environ,
    )

    assert build.returncode != 0
    assert 'includes a local:// reference that is not registered' in _unwrapped(build.stdout, build.stderr)


@pytest.mark.skipif(shutil.which('cmake') is None, reason='cmake not on PATH')
def test_macro_rejects_duplicate_resource_name(inner_pkg: Path):
    (inner_pkg / 'CMakeLists.txt').write_text(
        _INNER_CMAKELISTS.replace(
            'ament_nodl_register(bad_exe FILE bad.nodl.yaml)',
            'ament_nodl_register(dup_resource FILE first.nodl.yaml)\n    ament_nodl_register(dup_resource FILE second.nodl.yaml)',
        )
    )
    (inner_pkg / 'first.nodl.yaml').write_text(_LEAF_NODL)
    (inner_pkg / 'second.nodl.yaml').write_text(_LEAF_NODL)

    configure = _configure(inner_pkg)

    assert configure.returncode != 0
    assert 'rejection_fixture__dup_resource is already registered' in _unwrapped(configure.stderr)
    assert 'resource names must be unique within a package' in _unwrapped(configure.stderr)


@pytest.mark.skipif(shutil.which('cmake') is None, reason='cmake not on PATH')
def test_macro_rejects_same_file_under_two_names(inner_pkg: Path):
    (inner_pkg / 'CMakeLists.txt').write_text(
        _INNER_CMAKELISTS.replace(
            'ament_nodl_register(bad_exe FILE bad.nodl.yaml)',
            'ament_nodl_register(first_resource FILE leaf.nodl.yaml)\n    ament_nodl_register(second_resource FILE leaf.nodl.yaml)',
        )
    )
    (inner_pkg / 'leaf.nodl.yaml').write_text(_LEAF_NODL)

    configure = _configure(inner_pkg)

    assert configure.returncode != 0
    assert 'is already registered as rejection_fixture__first_resource' in _unwrapped(configure.stderr)


@pytest.mark.skipif(shutil.which('cmake') is None, reason='cmake not on PATH')
def test_macro_rejects_same_file_spelled_through_a_symlink(inner_pkg: Path):
    (inner_pkg / 'CMakeLists.txt').write_text(
        _INNER_CMAKELISTS.replace(
            'ament_nodl_register(bad_exe FILE bad.nodl.yaml)',
            'ament_nodl_register(first_resource FILE leaf.nodl.yaml)\n    ament_nodl_register(second_resource FILE link.nodl.yaml)',
        )
    )
    (inner_pkg / 'leaf.nodl.yaml').write_text(_LEAF_NODL)
    (inner_pkg / 'link.nodl.yaml').symlink_to('leaf.nodl.yaml')

    configure = _configure(inner_pkg)

    assert configure.returncode != 0
    assert 'is already registered as rejection_fixture__first_resource' in _unwrapped(configure.stderr)
