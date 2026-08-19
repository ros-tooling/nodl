# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Tests for the ``python -m nodl_schema.validator`` CLI used by build-time hooks."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_VALID = """\
nodl_version: 2
publishers:
  - name: /chatter
    type: std_msgs/msg/String
    qos:
      history: KEEP_LAST
      depth: 10
      reliability: RELIABLE
"""

_INVALID_BAD_PARAM_TYPE = """\
nodl_version: 2
parameters:
  speed:
    type: not_a_real_type
"""

_INVALID_NOT_A_MAPPING = '- just a list\n'

# A schema-valid document whose include cannot be resolved (no such package in the ament index).
_UNRESOLVABLE_INCLUDE = """\
nodl_version: 2
include:
  - ref: nodl://no_such_package/no_such_node
"""


def _run(file: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, '-m', 'nodl_schema', *args, str(file)],
        capture_output=True,
        text=True,
    )


def test_valid_file_exits_zero(tmp_path: Path):
    f = tmp_path / 'ok.nodl.yaml'
    f.write_text(_VALID)
    result = _run(f)
    assert result.returncode == 0, result.stderr
    assert str(f) in result.stdout


def test_invalid_schema_exits_one(tmp_path: Path):
    f = tmp_path / 'bad.nodl.yaml'
    f.write_text(_INVALID_BAD_PARAM_TYPE)
    result = _run(f)
    assert result.returncode == 1
    # The file path should be in the error so build logs are scannable.
    assert str(f) in result.stderr


def test_non_mapping_exits_one(tmp_path: Path):
    f = tmp_path / 'list.nodl.yaml'
    f.write_text(_INVALID_NOT_A_MAPPING)
    result = _run(f)
    assert result.returncode == 1
    assert str(f) in result.stderr


def test_missing_file_exits_one(tmp_path: Path):
    result = _run(tmp_path / 'does_not_exist.nodl.yaml')
    assert result.returncode == 1


def test_json_frontend_supported(tmp_path: Path):
    f = tmp_path / 'ok.nodl.json'
    f.write_text('{"nodl_version": 2}\n')
    result = _run(f)
    assert result.returncode == 0, result.stderr


def test_unresolvable_include_exits_one_by_default(tmp_path: Path):
    # a broken reference has to fail the build next to the schema check
    f = tmp_path / 'inc.nodl.yaml'
    f.write_text(_UNRESOLVABLE_INCLUDE)
    result = _run(f)
    assert result.returncode == 1
    assert str(f) in result.stderr


def test_no_resolve_skips_reference_resolution(tmp_path: Path):
    # --no-resolve checks the schema only, so an unresolvable include is fine.
    f = tmp_path / 'inc.nodl.yaml'
    f.write_text(_UNRESOLVABLE_INCLUDE)
    result = _run(f, '--no-resolve')
    assert result.returncode == 0, result.stderr


def test_malformed_ref_exits_one_even_with_no_resolve(tmp_path: Path):
    # The reference form is a schema constraint, so it is checked whether or not we resolve.
    f = tmp_path / 'bad_ref.nodl.yaml'
    f.write_text('nodl_version: 2\ninclude:\n  - ref: common/telemetry.nodl.yaml\n')
    assert _run(f, '--no-resolve').returncode == 1
