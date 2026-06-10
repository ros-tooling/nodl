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
    main:
      nodl_version: 2
      parameters:
        bad:
          type: not_a_real_type
""").lstrip()


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
