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
    # The default (resolving) path is what the CMake macro runs, so an unresolvable include must fail.
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


def test_relative_include_validates_against_the_source_tree(tmp_path: Path):
    # The whole point of the relative form: it resolves at build time, before anything is installed.
    (tmp_path / 'shared.nodl.yaml').write_text(_VALID)
    f = tmp_path / 'main.nodl.yaml'
    f.write_text('nodl_version: 2\ninclude:\n  - ref: shared.nodl.yaml\n')
    result = _run(f)
    assert result.returncode == 0, result.stderr


def test_missing_relative_include_exits_one(tmp_path: Path):
    f = tmp_path / 'main.nodl.yaml'
    f.write_text('nodl_version: 2\ninclude:\n  - ref: absent.nodl.yaml\n')
    result = _run(f)
    assert result.returncode == 1
    assert str(f) in result.stderr


# ---------------------------------------------------------------------------
# --list-references and --rewrite-to: the two modes ament_nodl_register_node uses
# ---------------------------------------------------------------------------


def test_list_references_reports_transitive_paths(tmp_path: Path):
    (tmp_path / 'leaf.nodl.yaml').write_text('nodl_version: 2\n')
    (tmp_path / 'mid.nodl.yaml').write_text('nodl_version: 2\ninclude:\n  - ref: leaf.nodl.yaml\n')
    f = tmp_path / 'main.nodl.yaml'
    f.write_text('nodl_version: 2\ninclude:\n  - ref: mid.nodl.yaml\n')

    result = _run(f, '--list-references')
    assert result.returncode == 0, result.stderr
    assert result.stdout.split() == [str(tmp_path / 'mid.nodl.yaml'), str(tmp_path / 'leaf.nodl.yaml')]


def test_list_references_is_empty_without_relative_includes(tmp_path: Path):
    f = tmp_path / 'main.nodl.yaml'
    f.write_text(_UNRESOLVABLE_INCLUDE)
    result = _run(f, '--list-references')
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == ''


def test_rewrite_emits_document_with_nodl_refs(tmp_path: Path):
    shared = tmp_path / 'common' / 'telemetry.nodl.yaml'
    shared.parent.mkdir()
    shared.write_text('nodl_version: 2\n')
    f = tmp_path / 'main.nodl.yaml'
    f.write_text('nodl_version: 2\ninclude:\n  - ref: common/telemetry.nodl.yaml\n')
    out = tmp_path / 'gen' / 'main.nodl.yaml'

    result = _run(f, '--rewrite-to', str(out), '--map', f'{shared}=my_pkg/telemetry')
    assert result.returncode == 0, result.stderr
    assert 'nodl://my_pkg/telemetry' in out.read_text()


def test_rewrite_without_relative_refs_copies_bytes(tmp_path: Path):
    # Most documents have nothing to rewrite; those must install exactly as authored.
    f = tmp_path / 'main.nodl.yaml'
    f.write_text(_VALID)
    out = tmp_path / 'out.nodl.yaml'
    assert _run(f, '--rewrite-to', str(out)).returncode == 0
    assert out.read_bytes() == f.read_bytes()


def test_rewrite_preserves_json_frontend(tmp_path: Path):
    shared = tmp_path / 'shared.nodl.yaml'
    shared.write_text('nodl_version: 2\n')
    f = tmp_path / 'main.nodl.json'
    f.write_text('{"nodl_version": 2, "include": [{"ref": "shared.nodl.yaml"}]}\n')
    out = tmp_path / 'out.nodl.json'

    assert _run(f, '--rewrite-to', str(out), '--map', f'{shared}=my_pkg/shared').returncode == 0
    text = out.read_text()
    assert '"nodl_version": 2' in text
    assert 'nodl://my_pkg/shared' in text


def test_rewrite_of_unregistered_reference_exits_one(tmp_path: Path):
    (tmp_path / 'shared.nodl.yaml').write_text('nodl_version: 2\n')
    f = tmp_path / 'main.nodl.yaml'
    f.write_text('nodl_version: 2\ninclude:\n  - ref: shared.nodl.yaml\n')
    result = _run(f, '--rewrite-to', str(tmp_path / 'out.nodl.yaml'))
    assert result.returncode == 1
    assert 'not registered' in result.stderr


def test_rewritten_document_still_validates(tmp_path: Path):
    # What gets installed has to be a valid NoDL document in its own right.
    shared = tmp_path / 'shared.nodl.yaml'
    shared.write_text('nodl_version: 2\n')
    f = tmp_path / 'main.nodl.yaml'
    f.write_text(f'{_VALID}include:\n  - ref: shared.nodl.yaml\n')
    out = tmp_path / 'out.nodl.yaml'

    assert _run(f, '--rewrite-to', str(out), '--map', f'{shared}=my_pkg/shared').returncode == 0
    result = _run(out, '--no-resolve')
    assert result.returncode == 0, result.stderr
