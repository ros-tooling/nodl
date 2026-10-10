# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest

MACRO = Path(__file__).parents[1] / 'cmake' / 'nodl_add_conformance_test.cmake'


# Stands in for launch_testing_ament_cmake, which sets PYTHON_EXECUTABLE in the scope that finds it.
FAKE_LAUNCH_TESTING = """
set(PYTHON_EXECUTABLE "/fake/python")
function(add_launch_test test_file)
  file(APPEND "${CMAKE_BINARY_DIR}/registration.txt"
    "${test_file}|python=${PYTHON_EXECUTABLE}|${ARGN}\n")
endfunction()
"""


def _configure(tmp_path: Path, invocation: str, *, create_nodl: bool = True, parameters_files: tuple[str, ...] = ()):
    prefix = tmp_path / 'prefix'
    package = prefix / 'share' / 'launch_testing_ament_cmake' / 'cmake'
    package.mkdir(parents=True)
    (package / 'launch_testing_ament_cmake-config.cmake').write_text(FAKE_LAUNCH_TESTING, encoding='utf-8')
    source = tmp_path / 'source'
    source.mkdir()
    if create_nodl:
        (source / "node's interface.nodl.yaml").write_text('nodl_version: 2\n', encoding='utf-8')
    for name in parameters_files:
        (source / name).write_text('{}\n', encoding='utf-8')
    cmakelists = textwrap.dedent(f"""
        cmake_minimum_required(VERSION 3.22)
        project(cmake_contract NONE)
        include("{MACRO.as_posix()}")
        {invocation}
    """)
    (source / 'CMakeLists.txt').write_text(cmakelists, encoding='utf-8')
    build = tmp_path / 'build'
    result = subprocess.run(
        ['cmake', '-S', str(source), '-B', str(build), f'-DCMAKE_PREFIX_PATH={prefix}'],
        capture_output=True,
        text=True,
        check=False,
    )
    return result, source, build


@pytest.mark.skipif(shutil.which('cmake') is None, reason='cmake not on PATH')
@pytest.mark.parametrize('missing', ['EXECUTABLE', 'NODL_FILE'])
def test_macro_rejects_each_missing_required_argument(tmp_path, missing):
    arguments = {
        'EXECUTABLE': 'fixture_node',
        'NODL_FILE': "node's interface.nodl.yaml",
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
    assert "_NODE_NAME = 'fixture'" in generated
    assert "_NODE_NAMESPACE = '/'" in generated
    assert "node\\'s interface.nodl.yaml'" in generated
    assert '_TIMEOUT = 15' in generated
    assert '_IGNORE = []' in generated
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
    assert "_NODE_NAME = 'fixture'" in generated
    assert "_NODE_NAMESPACE = '/robot'" in generated
    assert '_TIMEOUT = 40' in generated
    registration = (build / 'registration.txt').read_text(encoding='utf-8')
    assert 'TARGET;contract_test' in registration
    assert 'TIMEOUT;50' in registration


@pytest.mark.skipif(shutil.which('cmake') is None, reason='cmake not on PATH')
def test_macro_defaults_node_name_to_test_name(tmp_path):
    invocation = textwrap.dedent("""
        nodl_add_conformance_test(contract_test
          EXECUTABLE fixture_node
          NODL_FILE "node's interface.nodl.yaml"
        )
    """)

    result, _, build = _configure(tmp_path, invocation)

    assert result.returncode == 0, result.stderr
    generated = (build / 'nodl_conformance' / 'contract_test.py').read_text(encoding='utf-8')
    assert "_NODE_NAME = 'contract_test'" in generated


@pytest.mark.skipif(shutil.which('cmake') is None, reason='cmake not on PATH')
def test_macro_rejects_invalid_default_node_name(tmp_path):
    invocation = textwrap.dedent("""
        nodl_add_conformance_test(contract-test
          EXECUTABLE fixture_node
          NODL_FILE "node's interface.nodl.yaml"
        )
    """)

    result, _, _ = _configure(tmp_path, invocation)

    assert result.returncode != 0
    assert "test name 'contract-test' is not a valid node name, pass NODE_NAME" in ' '.join(result.stderr.split())


@pytest.mark.skipif(shutil.which('cmake') is None, reason='cmake not on PATH')
def test_macro_accepts_explicit_node_name_for_invalid_test_name(tmp_path):
    invocation = textwrap.dedent("""
        nodl_add_conformance_test(contract-test
          EXECUTABLE fixture_node
          NODL_FILE "node's interface.nodl.yaml"
          NODE_NAME fixture
        )
    """)

    result, _, build = _configure(tmp_path, invocation)

    assert result.returncode == 0, result.stderr
    generated = (build / 'nodl_conformance' / 'contract-test.py').read_text(encoding='utf-8')
    assert "_NODE_NAME = 'fixture'" in generated


@pytest.mark.skipif(shutil.which('cmake') is None, reason='cmake not on PATH')
def test_macro_can_be_called_more_than_once(tmp_path):
    invocation = textwrap.dedent("""
        foreach(name first second)
          nodl_add_conformance_test(${name}
            EXECUTABLE fixture_node
            NODL_FILE "node's interface.nodl.yaml"
            NODE_NAME ${name}
          )
        endforeach()
    """)

    result, _, build = _configure(tmp_path, invocation)

    assert result.returncode == 0, result.stderr
    registrations = (build / 'registration.txt').read_text(encoding='utf-8').splitlines()
    assert len(registrations) == 2
    assert all('python=/fake/python' in line for line in registrations)


@pytest.mark.skipif(shutil.which('cmake') is None, reason='cmake not on PATH')
def test_macro_passes_parameters_and_files_to_node(tmp_path):
    absolute = tmp_path / 'source' / 'other.yaml'
    invocation = textwrap.dedent(f"""
        nodl_add_conformance_test(contract_test
          EXECUTABLE fixture_node
          NODL_FILE "node's interface.nodl.yaml"
          NODE_NAME fixture
          PARAMETERS_FILE base.yaml "{absolute.as_posix()}"
          PARAMETERS
            limit:=5
            mode:=1_000
            [=[path:=it's a\\b/c "quoted"]=]
            [=[list:=[1, 2]]=]
            nested.name:=a:=b
        )
    """)

    result, source, build = _configure(tmp_path, invocation, parameters_files=('base.yaml', 'other.yaml'))

    assert result.returncode == 0, result.stderr
    generated = (build / 'nodl_conformance' / 'contract_test.py').read_text(encoding='utf-8')
    compile(generated, 'contract_test.py', 'exec')
    namespace: dict = {}
    for line in generated.splitlines():
        if line.startswith(('_PARAMETERS_FILES', '_PARAMETERS =')):
            exec(line, namespace)
    assert namespace['_PARAMETERS_FILES'] == [str(source / 'base.yaml'), str(absolute)]
    assert namespace['_PARAMETERS'] == [
        'limit:=5',
        'mode:=1_000',
        'path:=it\'s a\\b/c "quoted"',
        'list:=[1, 2]',
        'nested.name:=a:=b',
    ]


@pytest.mark.skipif(shutil.which('cmake') is None, reason='cmake not on PATH')
@pytest.mark.parametrize('item', ['no_separator', ':=value', 'name=value', 'name:='])
def test_macro_rejects_invalid_parameter_item(tmp_path, item):
    invocation = textwrap.dedent(f"""
        nodl_add_conformance_test(contract_test
          EXECUTABLE fixture_node
          NODL_FILE "node's interface.nodl.yaml"
          NODE_NAME fixture
          PARAMETERS ok:=1 {item}
        )
    """)

    result, _, _ = _configure(tmp_path, invocation)

    assert result.returncode != 0
    assert f"PARAMETERS item must be name:=value: '{item}'" in ' '.join(result.stderr.split())


@pytest.mark.skipif(shutil.which('cmake') is None, reason='cmake not on PATH')
def test_macro_rejects_missing_parameters_file(tmp_path):
    invocation = textwrap.dedent("""
        nodl_add_conformance_test(contract_test
          EXECUTABLE fixture_node
          NODL_FILE "node's interface.nodl.yaml"
          NODE_NAME fixture
          PARAMETERS_FILE missing.yaml
        )
    """)

    result, source, _ = _configure(tmp_path, invocation)

    assert result.returncode != 0
    assert f'PARAMETERS_FILE does not exist: {source / "missing.yaml"}' in ' '.join(result.stderr.split())


@pytest.mark.skipif(shutil.which('cmake') is None, reason='cmake not on PATH')
def test_macro_passes_ignore_rules_to_the_generated_test(tmp_path):
    invocation = textwrap.dedent("""
        nodl_add_conformance_test(contract_test
          EXECUTABLE fixture_node
          NODL_FILE "node's interface.nodl.yaml"
          NODE_NAME fixture
          IGNORE publisher:/topic_statistics "subscription:/it's/*" parameter:qos_overrides.*
        )
    """)

    result, _, build = _configure(tmp_path, invocation)

    assert result.returncode == 0, result.stderr
    generated = (build / 'nodl_conformance' / 'contract_test.py').read_text(encoding='utf-8')
    namespace: dict = {}
    for line in generated.splitlines():
        if line.startswith('_IGNORE = '):
            exec(line, namespace)
    assert namespace['_IGNORE'] == ['publisher:/topic_statistics', "subscription:/it's/*", 'parameter:qos_overrides.*']
    assert 'ignore=[*_IGNORE, *ignore_from_environment(os.environ)]' in generated
    compile(generated, 'contract_test.py', 'exec')
