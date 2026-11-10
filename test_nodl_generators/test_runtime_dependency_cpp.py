# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Check that ``nodl_generate_cpp`` requires the calling package to declare ``nodl_runtime_cpp``.

Configures a small inner package whose generated code includes ``nodl_runtime_cpp``, with different declarations.
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
    find_package(nodl_generator_cpp REQUIRED)
    nodl_generate_cpp(fixture_node_base {export} node.nodl.yaml)
    ament_package()
""")

PACKAGE_XML = textwrap.dedent("""\
    <?xml version="1.0"?>
    <package format="3">
      <name>runtime_dependency_fixture</name>
      <version>0.0.0</version>
      <description>Inner package checking the nodl_runtime_cpp dependency.</description>
      <maintainer email="test@example.com">test</maintainer>
      <license>Apache-2.0</license>
      <buildtool_depend>ament_cmake</buildtool_depend>
      <buildtool_depend>nodl_generator_cpp</buildtool_depend>
      <depend>rclcpp</depend>
      {runtime_depend}
      <export>
        <build_type>ament_cmake</build_type>
      </export>
    </package>
""")

PARAMETERS = """
parameters:
  speed:
    type: double
    default_value: 1.0
"""

NODL = {
    'parameters': 'nodl_version: 2\ninclude:\n  - ref: nodl://nodl_common_interfaces/node\n' + PARAMETERS,
    'lifecycle': 'nodl_version: 2\ninclude:\n  - ref: nodl://nodl_common_interfaces/lifecycle_node\n',
    'plain': 'nodl_version: 2\ninclude:\n  - ref: nodl://nodl_common_interfaces/node\n',
}

BUILD_DEPEND = '<build_depend>nodl_runtime_cpp</build_depend>'
DEPEND = '<depend>nodl_runtime_cpp</depend>'


def _configure(tmp_path: Path, nodl: str, runtime_depend: str, *, export: bool = False) -> subprocess.CompletedProcess:
    package = tmp_path / 'runtime_dependency_fixture'
    package.mkdir()
    (package / 'CMakeLists.txt').write_text(CMAKELISTS.format(export='EXPORT' if export else ''))
    (package / 'package.xml').write_text(PACKAGE_XML.format(runtime_depend=runtime_depend))
    (package / 'node.nodl.yaml').write_text(NODL[nodl])
    return subprocess.run(
        ['cmake', '-S', str(package), '-B', str(package / 'build')],
        capture_output=True,
        text=True,
        env=os.environ,
        check=False,
    )


@pytest.mark.parametrize('nodl', ['parameters', 'lifecycle'])
@pytest.mark.parametrize(
    ('runtime_depend', 'export'),
    [(DEPEND, False), (DEPEND, True), (BUILD_DEPEND, False)],
    ids=['depend', 'depend-export', 'build-depend'],
)
def test_declared_runtime_dependency_configures(tmp_path, nodl, runtime_depend, export):
    result = _configure(tmp_path, nodl, runtime_depend, export=export)

    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize('nodl', ['parameters', 'lifecycle'])
@pytest.mark.parametrize('export', [False, True], ids=['private', 'export'])
def test_missing_runtime_dependency_is_rejected(tmp_path, nodl, export):
    result = _configure(tmp_path, nodl, '', export=export)

    assert result.returncode != 0
    message = ' '.join(result.stderr.split())
    assert "package 'runtime_dependency_fixture' must declare a build dependency on nodl_runtime_cpp" in message
    assert 'Add <depend>nodl_runtime_cpp</depend> to its package.xml.' in message


def test_build_only_dependency_of_an_exported_target_is_rejected(tmp_path):
    result = _configure(tmp_path, 'parameters', BUILD_DEPEND, export=True)

    assert result.returncode != 0
    message = ' '.join(result.stderr.split())
    assert (
        "exports target 'fixture_node_base', so it must declare a build export dependency on nodl_runtime_cpp"
        in message
    )


def test_node_without_runtime_headers_needs_no_dependency(tmp_path):
    result = _configure(tmp_path, 'plain', '', export=True)

    assert result.returncode == 0, result.stderr
