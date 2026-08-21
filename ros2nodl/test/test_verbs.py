# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for the ros2nodl validate verb."""

import argparse

from ros2nodl.verb.validate import ValidateVerb


def _make_args(files=None, resolve=True):
    args = argparse.Namespace()
    args.files = files or []
    args.resolve = resolve
    return args


_UNRESOLVABLE_INCLUDE = 'nodl_version: 2\ninclude:\n  - ref: nodl://no_such_package/no_such_node\n'


class TestValidateVerb:
    def setup_method(self):
        self.verb = ValidateVerb()

    def test_valid_yaml_file(self, tmp_path):
        nodl_file = tmp_path / 'valid.yaml'
        nodl_file.write_text(
            'nodl_version: 2\n'
            'publishers:\n'
            '  - name: /t\n'
            '    type: std_msgs/msg/String\n'
            '    qos:\n'
            '      history: SYSTEM_DEFAULT\n'
            '      reliability: SYSTEM_DEFAULT\n'
        )
        result = self.verb.main(args=_make_args(files=[nodl_file]))
        assert result == 0

    def test_valid_json_file(self, tmp_path):
        nodl_file = tmp_path / 'valid.json'
        nodl_file.write_text(
            '{"nodl_version": 2, "publishers": ['
            '{"name": "/t", "type": "std_msgs/msg/String",'
            ' "qos": {"history": "SYSTEM_DEFAULT", "reliability": "SYSTEM_DEFAULT"}}]}'
        )
        result = self.verb.main(args=_make_args(files=[nodl_file]))
        assert result == 0

    def test_invalid_file_returns_1(self, tmp_path, capsys):
        nodl_file = tmp_path / 'bad.yaml'
        nodl_file.write_text('nodl_version: 2\nparameters:\n  p:\n    type: not_a_real_type\n')
        result = self.verb.main(args=_make_args(files=[nodl_file]))
        assert result == 1
        assert 'INVALID' in capsys.readouterr().err

    def test_minimal_document_is_valid(self, tmp_path):
        nodl_file = tmp_path / 'min.yaml'
        nodl_file.write_text('nodl_version: 2\n')
        result = self.verb.main(args=_make_args(files=[nodl_file]))
        assert result == 0

    def test_nonexistent_file_returns_1(self, capsys, tmp_path):
        result = self.verb.main(args=_make_args(files=[tmp_path / 'nonexistent.yaml']))
        assert result == 1
        assert 'No such file' in capsys.readouterr().err

    def test_success_prints_ok(self, tmp_path, capsys):
        nodl_file = tmp_path / 'ok.yaml'
        nodl_file.write_text('nodl_version: 2\n')
        self.verb.main(args=_make_args(files=[nodl_file]))
        assert 'ok' in capsys.readouterr().out

    def test_multiple_files_all_valid(self, tmp_path):
        a = tmp_path / 'a.yaml'
        b = tmp_path / 'b.yaml'
        a.write_text('nodl_version: 2\n')
        b.write_text('nodl_version: 2\n')
        result = self.verb.main(args=_make_args(files=[a, b]))
        assert result == 0

    def test_multiple_files_one_invalid_returns_1(self, tmp_path):
        good = tmp_path / 'good.yaml'
        bad = tmp_path / 'bad.yaml'
        good.write_text('nodl_version: 2\n')
        bad.write_text('nodl_version: 1\n')
        result = self.verb.main(args=_make_args(files=[good, bad]))
        assert result == 1

    def test_unresolvable_include_returns_1_by_default(self, tmp_path):
        nodl_file = tmp_path / 'inc.yaml'
        nodl_file.write_text(_UNRESOLVABLE_INCLUDE)
        result = self.verb.main(args=_make_args(files=[nodl_file]))
        assert result == 1

    def test_no_resolve_skips_reference_resolution(self, tmp_path):
        nodl_file = tmp_path / 'inc.yaml'
        nodl_file.write_text(_UNRESOLVABLE_INCLUDE)
        result = self.verb.main(args=_make_args(files=[nodl_file], resolve=False))
        assert result == 0
