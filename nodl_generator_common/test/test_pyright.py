# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Static type checking with pyright."""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

# The importable package source lives one level up from this test directory.
_SOURCE_DIR = Path(__file__).resolve().parent.parent


@pytest.mark.skipif(shutil.which('pyright') is None, reason='pyright is not installed')
def test_pyright():
    result = subprocess.run(
        ['pyright', str(_SOURCE_DIR)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    # Echo pyright's report so failures are actionable in the test log.
    print(result.stdout, file=sys.stderr)
    assert result.returncode == 0, 'pyright found type errors'
