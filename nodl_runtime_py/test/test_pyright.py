# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Static type checking with pyright."""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

_PACKAGE_DIR = Path(__file__).resolve().parent.parent
_EXAMPLES_DIR = _PACKAGE_DIR / 'doc' / 'examples'


# The examples import each other, so pyright runs from their directory.
@pytest.mark.skipif(shutil.which('pyright') is None, reason='pyright is not installed')
@pytest.mark.parametrize(
    'source_dir, working_dir',
    [(_PACKAGE_DIR / 'nodl_runtime_py', _PACKAGE_DIR), (_EXAMPLES_DIR, _EXAMPLES_DIR)],
    ids=['package', 'examples'],
)
def test_pyright(source_dir, working_dir):
    result = subprocess.run(
        ['pyright', str(source_dir)],
        cwd=working_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    # Echo pyright's report so failures are actionable in the test log.
    print(result.stdout, file=sys.stderr)
    assert result.returncode == 0, 'pyright found type errors'
