# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest

MACRO = Path(__file__).parents[1] / 'cmake' / 'nodl_add_conformance_test.cmake'


def _configure(tmp_path: Path, invocation: str, *, create_nodl: bool = True):
    source = tmp_path / 'source'
    source.mkdir()
    if create_nodl:
        (source / "node's interface.nodl.yaml").write_text('nodl_version: 2\n', encoding='utf-8')
    cmakelists = textwrap.dedent(f"""
        cmake_minimum_required(VERSION 3.22)
        project(cmake_contract NONE)
        function(add_launch_test test_file)
          file(WRITE "${{CMAKE_BINARY_DIR}}/registration.txt"
            "${{test_file}}|${{ARGN}}")
        endfunction()
        include("{MACRO.as_posix()}")
        {invocation}
    """)
    (source / 'CMakeLists.txt').write_text(cmakelists, encoding='utf-8')
    build = tmp_path / 'build'
    result = subprocess.run(
        ['cmake', '-S', str(source), '-B', str(build)],
        capture_output=True,
        text=True,
        check=False,
    )
    return result, source, build


@pytest.mark.skipif(shutil.which('cmake') is None, reason='cmake not on PATH')
@pytest.mark.parametrize('missing', ['EXECUTABLE', 'NODL_FILE', 'NODE_NAME'])
def test_macro_rejects_each_missing_required_argument(tmp_path, missing):
    arguments = {
        'EXECUTABLE': 'fixture_node',
        'NODL_FILE': "node's interface.nodl.yaml",
        'NODE_NAME': 'fixture',
    }
    del arguments[missing]
    invocation = 'nodl_add_conformance_test(contract_test\n'
    invocation += ''.join(f'  {key} "{value}"\n' for key, value in arguments.items())
    invocation += ')'

    result, _, _ = _configure(tmp_path, invocation)

    assert result.returncode != 0
    assert f'{missing} is required' in result.stderr


@pytest.mark.skipif(shutil.which('cmake') is None, reason='cmake not on PATH')
def test_macro_rejects_missing_resolved_file(tmp_path):
    invocation = textwrap.dedent("""
        nodl_add_conformance_test(contract_test
          EXECUTABLE fixture_node
          NODL_FILE missing.nodl.yaml
          NODE_NAME fixture
        )
    """)

    result, source, _ = _configure(tmp_path, invocation, create_nodl=False)

    assert result.returncode != 0
    assert str(source / 'missing.nodl.yaml') in result.stderr


@pytest.mark.skipif(shutil.which('cmake') is None, reason='cmake not on PATH')
@pytest.mark.parametrize('timeout', ['0', '1.5', 'invalid'])
def test_macro_rejects_invalid_timeout(tmp_path, timeout):
    invocation = textwrap.dedent(f"""
        nodl_add_conformance_test(contract_test
          EXECUTABLE fixture_node
          NODL_FILE "node's interface.nodl.yaml"
          NODE_NAME fixture
          TIMEOUT {timeout}
        )
    """)

    result, _, _ = _configure(tmp_path, invocation)

    assert result.returncode != 0
    assert 'TIMEOUT must be a positive integer' in result.stderr


@pytest.mark.skipif(shutil.which('cmake') is None, reason='cmake not on PATH')
def test_macro_generates_launch_test_and_registration(tmp_path):
    invocation = textwrap.dedent("""
        nodl_add_conformance_test(contract_test
          EXECUTABLE fixture_node
          NODL_FILE "node's interface.nodl.yaml"
          NODE_NAME fixture
        )
    """)

    result, source, build = _configure(tmp_path, invocation)

    assert result.returncode == 0, result.stderr
    generated = (build / 'nodl_conformance' / 'contract_test.py').read_text(encoding='utf-8')
    assert "_PACKAGE = 'cmake_contract'" in generated
    assert "_NODE_NAMESPACE = '/'" in generated
    assert "node\\'s interface.nodl.yaml'" in generated
    assert '_TIMEOUT = 15' in generated
    assert 'from ros2nodl.conformance import assert_conforms' in generated
    assert 'from launch_ros.actions import Node' in generated
    assert 'assert_conforms(' in generated
    compile(generated, 'contract_test.py', 'exec')
    registration = (build / 'registration.txt').read_text(encoding='utf-8')
    assert str(source / "node's interface.nodl.yaml") not in registration
    assert 'TARGET;contract_test' in registration
    assert 'TIMEOUT;25' in registration


@pytest.mark.skipif(shutil.which('cmake') is None, reason='cmake not on PATH')
def test_macro_accepts_explicit_values_and_absolute_file(tmp_path):
    absolute = tmp_path / 'source' / "node's interface.nodl.yaml"
    invocation = textwrap.dedent(f"""
        nodl_add_conformance_test(contract_test
          PACKAGE explicit_package
          EXECUTABLE fixture_node
          NODL_FILE "{absolute.as_posix()}"
          NODE_NAME fixture
          NODE_NAMESPACE /robot
          TIMEOUT 40
        )
    """)

    result, _, build = _configure(tmp_path, invocation)

    assert result.returncode == 0, result.stderr
    generated = (build / 'nodl_conformance' / 'contract_test.py').read_text(encoding='utf-8')
    assert "_PACKAGE = 'explicit_package'" in generated
    assert "_NODE_NAMESPACE = '/robot'" in generated
    assert '_TIMEOUT = 40' in generated
    registration = (build / 'registration.txt').read_text(encoding='utf-8')
    assert 'TARGET;contract_test' in registration
    assert 'TIMEOUT;50' in registration
