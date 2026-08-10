# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""End-to-end test that the ament_nodl_register_node macro propagates validator failures as build failures.

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
    ament_nodl_register_node(bad_exe FILE bad.nodl.yaml)
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


_VALID_NODL = 'nodl_version: 2\n'

# composed.nodl.yaml references shared.nodl.yaml, but nothing registers shared.nodl.yaml.
# There is no name to rewrite the reference to, so this must fail at configure time.
_UNREGISTERED_REF_CMAKELISTS = textwrap.dedent("""
    cmake_minimum_required(VERSION 3.22)
    project(rejection_fixture)
    find_package(ament_cmake REQUIRED)
    find_package(ament_nodl REQUIRED)
    ament_nodl_register_node(composed FILE composed.nodl.yaml)
    ament_package()
""")

# Two different files claiming the name 'thing'. The second would take over a name that an
# already-rewritten reference could point at, so it must fail at configure time.
_DUPLICATE_NAME_CMAKELISTS = textwrap.dedent("""
    cmake_minimum_required(VERSION 3.22)
    project(rejection_fixture)
    find_package(ament_cmake REQUIRED)
    find_package(ament_nodl REQUIRED)
    ament_nodl_register_node(thing FILE one.nodl.yaml)
    ament_nodl_register_node(thing FILE two.nodl.yaml)
    ament_package()
""")


def _configure(pkg: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ['cmake', '-S', str(pkg), '-B', str(pkg / 'build')],
        capture_output=True,
        text=True,
        env=os.environ,
    )


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


@pytest.mark.skipif(shutil.which('cmake') is None, reason='cmake not on PATH')
def test_macro_rejects_reference_to_unregistered_document(tmp_path: Path):
    # The error belongs at configure time, because the fix is the order of calls in CMakeLists.
    pkg = tmp_path / 'rejection_fixture'
    pkg.mkdir()
    (pkg / 'CMakeLists.txt').write_text(_UNREGISTERED_REF_CMAKELISTS)
    (pkg / 'package.xml').write_text(_INNER_PACKAGE_XML)
    (pkg / 'shared.nodl.yaml').write_text(_VALID_NODL)
    (pkg / 'composed.nodl.yaml').write_text('nodl_version: 2\ninclude:\n  - ref: local://shared.nodl.yaml\n')

    result = _configure(pkg)
    assert result.returncode != 0, 'Expected configure to fail on the unregistered reference'
    combined = result.stdout + result.stderr
    assert 'not registered' in combined, f'Expected an unregistered-reference error, got:\n{combined}'
    assert 'shared.nodl.yaml' in combined


@pytest.mark.skipif(shutil.which('cmake') is None, reason='cmake not on PATH')
def test_macro_rejects_one_name_registered_from_two_files(tmp_path: Path):
    pkg = tmp_path / 'rejection_fixture'
    pkg.mkdir()
    (pkg / 'CMakeLists.txt').write_text(_DUPLICATE_NAME_CMAKELISTS)
    (pkg / 'package.xml').write_text(_INNER_PACKAGE_XML)
    (pkg / 'one.nodl.yaml').write_text(_VALID_NODL)
    (pkg / 'two.nodl.yaml').write_text(_VALID_NODL)

    result = _configure(pkg)
    assert result.returncode != 0, 'Expected configure to fail on the duplicate name'
    combined = result.stdout + result.stderr
    assert 'already registered' in combined, f'Expected a duplicate-name error, got:\n{combined}'
