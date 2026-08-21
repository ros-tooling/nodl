# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for the reference rewrite core.

These exercise the rewriter directly with synthetic rewrite rules, so no ament index is involved.
The integration between the rules and what registration installs is covered in test_ament_nodl.
"""

import argparse

import pytest
import yaml

from ros2nodl.verb.rewrite import RewriteVerb, parse_reference_arg

_LEAF = 'nodl_version: 2\ndescription: Leaf document.\n'


def _write(path, text):
    path.write_text(text)
    return path


class TestParseReferenceArg:
    def test_splits_on_walrus(self):
        assert parse_reference_arg('local:///a/b.yaml:=nodl://p/n') == ('local:///a/b.yaml', 'nodl://p/n')

    @pytest.mark.parametrize('bad', ['no-separator', ':=only-to', 'only-from:=', ''])
    def test_rejects_malformed(self, bad):
        with pytest.raises(ValueError, match='expected FROM:=TO'):
            parse_reference_arg(bad)


class TestRewriteVerb:
    def _args(self, source, references, output):
        args = argparse.Namespace()
        args.source = source
        args.references = references
        args.output = output
        return args

    def test_writes_rewritten_output(self, tmp_path):
        leaf = _write(tmp_path / 'leaf.nodl.yaml', _LEAF)
        root = _write(
            tmp_path / 'root.nodl.yaml',
            'nodl_version: 2\ninclude:\n  - ref: local://leaf.nodl.yaml\n',
        )
        output = tmp_path / 'out' / 'rewritten'
        rc = RewriteVerb().main(args=self._args(root, [f'local://{leaf}:=nodl://mypkg/leaf'], output))
        assert rc == 0
        assert yaml.safe_load(output.read_text())['include'] == [{'ref': 'nodl://mypkg/leaf'}]

    def test_failure_returns_nonzero_and_writes_nothing(self, tmp_path, capsys):
        _write(tmp_path / 'leaf.nodl.yaml', _LEAF)
        root = _write(
            tmp_path / 'root.nodl.yaml',
            'nodl_version: 2\ninclude:\n  - ref: local://leaf.nodl.yaml\n',
        )
        output = tmp_path / 'out'
        rc = RewriteVerb().main(args=self._args(root, [], output))
        assert rc == 1
        assert not output.exists()
