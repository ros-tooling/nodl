# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0

"""Argument-validation tests for the ``nodl_generate_cpp`` CMake macro.

Each case runs the macro from a ``cmake -P`` script.
Validation happens before any target or process is created, so script mode reaches it.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

MACRO_FILE = Path(__file__).parent.parent / 'cmake' / 'nodl_generate_cpp.cmake'

pytestmark = pytest.mark.skipif(shutil.which('cmake') is None, reason='cmake not on PATH')


def _run_macro(tmp_path: Path, call_args: str) -> subprocess.CompletedProcess:
    script = tmp_path / 'call.cmake'
    script.write_text(f'include("{MACRO_FILE.as_posix()}")\nnodl_generate_cpp({call_args})\n')
    return subprocess.run(
        ['cmake', '-P', str(script)],
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.parametrize(
    ('call_args', 'expected'),
    [
        ('my_base SHARED STATIC my.nodl.yaml', "target 'my_base' cannot be both SHARED and STATIC"),
        ('my_base', "target 'my_base' requires exactly one NODL_FILE, got 0"),
        ('my_base STATIC', "target 'my_base' requires exactly one NODL_FILE, got 0"),
        ('my_base a.nodl.yaml b.nodl.yaml', "target 'my_base' requires exactly one NODL_FILE, got 2"),
    ],
    ids=['shared-and-static', 'missing-file', 'missing-file-with-type', 'two-files'],
)
def test_bad_arguments_are_rejected(tmp_path, call_args, expected):
    result = _run_macro(tmp_path, call_args)

    assert result.returncode != 0
    assert 'nodl_generate_cpp:' in result.stderr
    assert expected in result.stderr
