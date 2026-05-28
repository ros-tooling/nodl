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


def _run(file: Path, *, fragment: bool = False) -> subprocess.CompletedProcess:
    cmd = [sys.executable, '-m', 'nodl_schema']
    if fragment:
        cmd.append('--fragment')
    cmd.append(str(file))
    return subprocess.run(cmd, capture_output=True, text=True)


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


# ---------------------------------------------------------------------------
# --fragment mode
# ---------------------------------------------------------------------------


def test_valid_fragment_exits_zero(tmp_path: Path):
    # A fragment with publishers / subscriptions but no base/fragments passes.
    f = tmp_path / 'frag.nodl.yaml'
    f.write_text(_VALID)
    result = _run(f, fragment=True)
    assert result.returncode == 0, result.stderr


def test_fragment_with_base_rejected(tmp_path: Path):
    f = tmp_path / 'bad_frag.nodl.yaml'
    f.write_text('nodl_version: 2\nbase: node\n')
    result = _run(f, fragment=True)
    assert result.returncode == 1
    assert str(f) in result.stderr
    assert "'base'" in result.stderr


def test_fragment_with_fragments_rejected(tmp_path: Path):
    f = tmp_path / 'bad_frag.nodl.yaml'
    f.write_text('nodl_version: 2\nfragments:\n  - ref: nodl://pkg/other\n')
    result = _run(f, fragment=True)
    assert result.returncode == 1
    assert "'fragments'" in result.stderr


def test_fragment_with_invalid_schema_still_rejected(tmp_path: Path):
    # Schema validation happens before the fragment-only check.
    f = tmp_path / 'doubly_bad.nodl.yaml'
    f.write_text(_INVALID_BAD_PARAM_TYPE)
    result = _run(f, fragment=True)
    assert result.returncode == 1
