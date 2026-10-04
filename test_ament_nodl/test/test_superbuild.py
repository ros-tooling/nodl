# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Registration from packages that are not the top-level project.

Writes a superbuild root that does not itself find ament_cmake and adds two packages with ``add_subdirectory``.
One package registers a document from a subdirectory of its own, so the test covers registrations spread over directories.
Both packages must configure, build, and install their own documents.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest

_SUPERBUILD_CMAKELISTS = textwrap.dedent("""
    cmake_minimum_required(VERSION 3.22)
    project(superbuild NONE)
    add_subdirectory(first_pkg)
    add_subdirectory(second_pkg)
""")

_PACKAGE_CMAKELISTS = textwrap.dedent("""
    cmake_minimum_required(VERSION 3.22)
    project({name})
    find_package(ament_cmake REQUIRED)
    find_package(ament_nodl REQUIRED)
    ament_nodl_register(top FILE top.nodl.yaml)
    {extra}
    ament_package()
""")

_PACKAGE_XML = textwrap.dedent("""<?xml version="1.0"?>
    <package format="3">
      <name>{name}</name>
      <version>0.0.0</version>
      <description>Package inside the superbuild fixture of test_ament_nodl.</description>
      <maintainer email="test@example.com">test</maintainer>
      <license>Apache-2.0</license>
      <buildtool_depend>ament_cmake</buildtool_depend>
      <buildtool_depend>ament_nodl</buildtool_depend>
      <export>
        <build_type>ament_cmake</build_type>
      </export>
    </package>
""").lstrip()

_LEAF = 'nodl_version: 2\ndescription: {name} leaf.\n'
_TOP_WITH_INCLUDE = 'nodl_version: 2\ndescription: {name} top.\ninclude:\n  - ref: local://sub/leaf.nodl.yaml\n'
_TOP = 'nodl_version: 2\ndescription: {name} top.\n'


def _write_package(root: Path, name: str, with_subdirectory: bool) -> None:
    pkg = root / name
    pkg.mkdir()
    (pkg / 'package.xml').write_text(_PACKAGE_XML.format(name=name))
    extra = ''
    top = _TOP
    if with_subdirectory:
        (pkg / 'sub').mkdir()
        (pkg / 'sub' / 'CMakeLists.txt').write_text('ament_nodl_register(leaf FILE leaf.nodl.yaml)\n')
        (pkg / 'sub' / 'leaf.nodl.yaml').write_text(_LEAF.format(name=name))
        extra = 'add_subdirectory(sub)'
        top = _TOP_WITH_INCLUDE
    (pkg / 'CMakeLists.txt').write_text(_PACKAGE_CMAKELISTS.format(name=name, extra=extra))
    (pkg / 'top.nodl.yaml').write_text(top.format(name=name))


@pytest.fixture
def superbuild(tmp_path: Path) -> Path:
    root = tmp_path / 'superbuild'
    root.mkdir()
    (root / 'CMakeLists.txt').write_text(_SUPERBUILD_CMAKELISTS)
    _write_package(root, 'first_pkg', with_subdirectory=True)
    _write_package(root, 'second_pkg', with_subdirectory=False)
    return root


def _run(*command: str) -> None:
    result = subprocess.run(command, capture_output=True, text=True, env=os.environ)
    assert result.returncode == 0, f'{" ".join(command)} failed:\n{result.stdout}\n{result.stderr}'


@pytest.mark.skipif(shutil.which('cmake') is None, reason='cmake not on PATH')
def test_packages_in_a_superbuild_register_and_install_their_documents(superbuild: Path, tmp_path: Path):
    build = tmp_path / 'build'
    prefix = tmp_path / 'prefix'

    _run('cmake', '-S', str(superbuild), '-B', str(build))
    _run('cmake', '--build', str(build))
    _run('cmake', '--install', str(build), '--prefix', str(prefix))

    index = prefix / 'share' / 'ament_index' / 'resource_index' / 'nodl'
    assert {p.name for p in index.iterdir()} == {
        'first_pkg__top',
        'first_pkg__leaf',
        'second_pkg__top',
    }
    # A package's includes are rewritten against its own registrations only.
    assert 'ref: nodl://first_pkg/leaf' in (index / 'first_pkg__top').read_text()
    assert (prefix / 'share' / 'first_pkg' / 'nodl' / 'leaf.nodl.yaml').is_file()
    assert (prefix / 'share' / 'second_pkg' / 'nodl' / 'top.nodl.yaml').is_file()
