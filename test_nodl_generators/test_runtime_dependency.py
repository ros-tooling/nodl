# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Check that ``nodl_generate_py`` requires the calling package to declare ``nodl_runtime_py``.

Configures a small inner package with and without the dependency.
"""

import os
import subprocess
import textwrap
from pathlib import Path

import pytest

CMAKELISTS = textwrap.dedent("""
    cmake_minimum_required(VERSION 3.22)
    project(runtime_dependency_fixture)
    find_package(ament_cmake REQUIRED)
    find_package(nodl_generator_py REQUIRED)
    nodl_generate_py(fixture_node_base node.nodl.yaml)
    ament_package()
""")

PACKAGE_XML = textwrap.dedent("""\
    <?xml version="1.0"?>
    <package format="3">
      <name>runtime_dependency_fixture</name>
      <version>0.0.0</version>
      <description>Inner package checking the nodl_runtime_py dependency.</description>
      <maintainer email="test@example.com">test</maintainer>
      <license>Apache-2.0</license>
      <buildtool_depend>ament_cmake</buildtool_depend>
      <buildtool_depend>nodl_generator_py</buildtool_depend>
      {runtime_depend}
      <export>
        <build_type>ament_cmake</build_type>
      </export>
    </package>
""")


def _configure(tmp_path: Path, runtime_depend: str) -> subprocess.CompletedProcess:
    package = tmp_path / 'runtime_dependency_fixture'
    package.mkdir()
    (package / 'CMakeLists.txt').write_text(CMAKELISTS)
    (package / 'package.xml').write_text(PACKAGE_XML.format(runtime_depend=runtime_depend))
    (package / 'node.nodl.yaml').write_text('nodl_version: 2\n')
    return subprocess.run(
        ['cmake', '-S', str(package), '-B', str(package / 'build')],
        capture_output=True,
        text=True,
        env=os.environ,
        check=False,
    )


@pytest.mark.parametrize(
    'runtime_depend',
    ['<exec_depend>nodl_runtime_py</exec_depend>', '<depend>nodl_runtime_py</depend>'],
    ids=['exec-depend', 'depend'],
)
def test_declared_runtime_dependency_configures(tmp_path, runtime_depend):
    result = _configure(tmp_path, runtime_depend)

    assert result.returncode == 0, result.stderr


def test_missing_runtime_dependency_is_rejected(tmp_path):
    result = _configure(tmp_path, '')

    assert result.returncode != 0
    message = ' '.join(result.stderr.split())
    assert "package 'runtime_dependency_fixture' must declare a runtime dependency on nodl_runtime_py" in message
    assert 'Add <exec_depend>nodl_runtime_py</exec_depend> to its package.xml.' in message
