# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0

"""Argument-validation tests for the ``nodl_generate_py`` and ``nodl_add_py_executable`` CMake functions.

Each case runs the function from a ``cmake -P`` script.
A stub stands in for ``ament_package_xml``, which script mode lacks, and declares the ``nodl_runtime_py`` dependency.
Validation happens before any process is run, so script mode reaches it.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

CMAKE_DIR = Path(__file__).parent.parent / 'cmake'
FUNCTION_FILE = CMAKE_DIR / 'nodl_generate_py.cmake'
EXECUTABLE_FUNCTION_FILE = CMAKE_DIR / 'nodl_add_py_executable.cmake'

pytestmark = pytest.mark.skipif(shutil.which('cmake') is None, reason='cmake not on PATH')


def _run_function(
    tmp_path: Path, call_args: str, function_file: Path = FUNCTION_FILE, function: str = 'nodl_generate_py'
) -> subprocess.CompletedProcess:
    script = tmp_path / 'call.cmake'
    script.write_text(
        f'cmake_minimum_required(VERSION 3.22)\n'
        f'macro(ament_package_xml)\n'
        f'  set(stub_EXEC_DEPENDS nodl_runtime_py)\n'
        f'endmacro()\n'
        f'set(PROJECT_NAME stub)\n'
        f'include("{function_file.as_posix()}")\n'
        f'{function}({call_args})\n'
    )
    return subprocess.run(
        ['cmake', '-P', str(script)],
        capture_output=True,
        text=True,
        check=False,
        cwd=tmp_path,
    )


@pytest.mark.parametrize(
    ('call_args', 'expected'),
    [
        ('my_base my.nodl.yaml EXPORT', 'unknown arguments: EXPORT'),
        ('my_base my.nodl.yaml STATIC NO_INDEX', 'unknown arguments: STATIC'),
        ('my_base my.nodl.yaml extra.nodl.yaml', 'unknown arguments: extra.nodl.yaml'),
        ('my_base my.nodl.yaml RESOURCE_NAME', "target 'my_base' has a RESOURCE_NAME with no value"),
    ],
    ids=['unknown-keyword', 'unknown-keyword-with-no-index', 'extra-positional', 'resource-name-without-value'],
)
def test_bad_arguments_are_rejected(tmp_path, call_args, expected):
    result = _run_function(tmp_path, call_args)

    assert result.returncode != 0
    assert expected in ' '.join(result.stderr.split())


@pytest.mark.parametrize(
    ('call_args', 'name'),
    [
        ('my_base my.nodl.yaml NO_INDEX RESOURCE_NAME my_node', 'my_node'),
        ('my_base my.nodl.yaml RESOURCE_NAME my_node NO_INDEX', 'my_node'),
        ('my_base my.nodl.yaml NO_INDEX RESOURCE_NAME off', 'off'),
        ('my_base my.nodl.yaml NO_INDEX RESOURCE_NAME 0', '0'),
    ],
    ids=['default', 'reversed', 'falsy-name-off', 'falsy-name-zero'],
)
def test_resource_name_with_no_index_is_rejected(tmp_path, call_args, name):
    result = _run_function(tmp_path, call_args)

    assert result.returncode != 0
    assert f"RESOURCE_NAME '{name}' has no effect" in ' '.join(result.stderr.split())


@pytest.mark.parametrize(
    'call_args',
    [
        'my_base my.nodl.yaml',
        'my_base my.nodl.yaml NO_INDEX',
        'my_base my.nodl.yaml RESOURCE_NAME my_node',
        'my_base my.nodl.yaml RESOURCE_NAME off',
        'my_base my.nodl.yaml RESOURCE_NAME 0',
    ],
    ids=['default-name', 'no-index', 'resource-name', 'resource-name-off', 'resource-name-zero'],
)
def test_valid_index_arguments_pass_validation(tmp_path, call_args):
    result = _run_function(tmp_path, call_args)

    # The function goes on to run the generator, which fails for lack of a Python interpreter.
    assert 'has no effect' not in result.stderr
    assert 'unknown arguments' not in result.stderr
    assert '--cmake-deps failed' in result.stderr


@pytest.mark.parametrize(
    ('call_args', 'expected'),
    [
        ('my_exe my_pkg:MyNode EXPORT', 'unknown arguments: EXPORT'),
        ('my_exe my_pkg:MyNode EXECUTOR a:A extra', 'unknown arguments: extra'),
        ('my_exe my_pkg:MyNode EXECUTOR', "executable 'my_exe' has an EXECUTOR with no value"),
    ],
    ids=['unknown-keyword', 'extra-positional', 'executor-without-value'],
)
def test_executable_bad_arguments_are_rejected(tmp_path, call_args, expected):
    result = _run_function(tmp_path, call_args, EXECUTABLE_FUNCTION_FILE, 'nodl_add_py_executable')

    assert result.returncode != 0
    assert expected in ' '.join(result.stderr.split())


@pytest.mark.parametrize(
    'call_args',
    ['my_exe my_pkg:MyNode', 'my_exe my_pkg:MyNode EXECUTOR rclpy.executors:MultiThreadedExecutor'],
    ids=['default-executor', 'executor'],
)
def test_executable_valid_arguments_pass_validation(tmp_path, call_args):
    result = _run_function(tmp_path, call_args, EXECUTABLE_FUNCTION_FILE, 'nodl_add_py_executable')

    # The function goes on to add a build rule, which script mode does not support.
    assert 'unknown arguments' not in result.stderr
    assert 'with no value' not in result.stderr
    assert 'add_custom_command command is not scriptable' in result.stderr
