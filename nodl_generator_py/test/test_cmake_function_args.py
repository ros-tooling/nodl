# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0

"""Argument-validation tests for the ``nodl_generate_py`` CMake function.

Each case runs the function from a ``cmake -P`` script.
Validation happens before any process is run, so script mode reaches it.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

FUNCTION_FILE = Path(__file__).parent.parent / 'cmake' / 'nodl_generate_py.cmake'

pytestmark = pytest.mark.skipif(shutil.which('cmake') is None, reason='cmake not on PATH')


def _run_function(tmp_path: Path, call_args: str) -> subprocess.CompletedProcess:
    script = tmp_path / 'call.cmake'
    script.write_text(f'include("{FUNCTION_FILE.as_posix()}")\nnodl_generate_py({call_args})\n')
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
