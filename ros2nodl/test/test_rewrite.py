# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for the reference rewrite core.

These exercise the rewriter directly with synthetic rewrite rules, so no ament index is involved.
The integration between the rules and what registration installs is covered in test_ament_nodl.
"""

import argparse

import pytest
from ruamel.yaml import YAML

from ros2nodl.rewrite import RewriteError, parse_reference_arg, rewrite_references
from ros2nodl.verb.rewrite import RewriteVerb

_LEAF = 'nodl_version: 2\ndescription: Leaf document.\n'


def _write(path, text):
    path.write_text(text)
    return path


def _load(text):
    return YAML(typ='safe').load(text)


class TestRewriteReferences:
    def test_local_include_is_rewritten_to_nodl_ref(self, tmp_path):
        leaf = _write(tmp_path / 'leaf.nodl.yaml', _LEAF)
        root = _write(
            tmp_path / 'root.nodl.yaml',
            'nodl_version: 2\ninclude:\n  - ref: local://leaf.nodl.yaml\n',
        )
        result = rewrite_references(root, {f'local://{leaf}': 'nodl://mypkg/leaf'})
        assert _load(result)['include'] == [{'ref': 'nodl://mypkg/leaf'}]

    def test_comments_and_key_order_survive(self, tmp_path):
        leaf = _write(tmp_path / 'leaf.nodl.yaml', _LEAF)
        root = _write(
            tmp_path / 'root.nodl.yaml',
            'nodl_version: 2\n'
            '# a standing comment\n'
            'description: preserve me\n'
            'include:\n'
            '  - ref: local://leaf.nodl.yaml  # inline note\n',
        )
        result = rewrite_references(root, {f'local://{leaf}': 'nodl://mypkg/leaf'})
        assert '# a standing comment' in result
        assert '# inline note' in result
        assert 'nodl://mypkg/leaf' in result
        assert 'local://' not in result

    def test_json_input_is_installed_as_yaml(self, tmp_path):
        leaf = _write(tmp_path / 'leaf.nodl.json', '{"nodl_version": 2}')
        root = _write(
            tmp_path / 'root.nodl.json',
            '{"nodl_version": 2, "include": [{"ref": "local://leaf.nodl.json"}]}',
        )
        result = rewrite_references(root, {f'local://{leaf}': 'nodl://mypkg/leaf'})
        # Output is YAML, not JSON, and the reference is rewritten.
        assert not result.lstrip().startswith('{')
        assert _load(result)['include'] == [{'ref': 'nodl://mypkg/leaf'}]

    def test_nodl_to_nodl_rename_is_supported(self, tmp_path):
        # The rewriter is generic: any scheme can be renamed, not just local://.
        root = _write(
            tmp_path / 'root.nodl.yaml',
            'nodl_version: 2\ninclude:\n  - ref: nodl://old/dep\n',
        )
        result = rewrite_references(root, {'nodl://old/dep': 'nodl://new/dep'})
        assert _load(result)['include'] == [{'ref': 'nodl://new/dep'}]

    def test_unmatched_nodl_ref_is_left_untouched(self, tmp_path):
        root = _write(
            tmp_path / 'root.nodl.yaml',
            'nodl_version: 2\ninclude:\n  - ref: nodl://external/dep\n',
        )
        result = rewrite_references(root, {})
        assert _load(result)['include'] == [{'ref': 'nodl://external/dep'}]

    def test_surviving_local_ref_fails(self, tmp_path):
        _write(tmp_path / 'leaf.nodl.yaml', _LEAF)
        root = _write(
            tmp_path / 'root.nodl.yaml',
            'nodl_version: 2\ninclude:\n  - ref: local://leaf.nodl.yaml\n',
        )
        # No rule covers the local include, so it would not resolve after install.
        with pytest.raises(RewriteError, match='unresolved local reference'):
            rewrite_references(root, {})

    def test_invalid_source_raises(self, tmp_path):
        root = _write(tmp_path / 'bad.nodl.yaml', 'nodl_version: 2\nparameters:\n  p:\n    type: not_a_type\n')
        with pytest.raises(Exception):
            rewrite_references(root, {})

    def test_document_with_no_includes_round_trips(self, tmp_path):
        root = _write(tmp_path / 'root.nodl.yaml', _LEAF)
        result = rewrite_references(root, {})
        assert _load(result)['description'] == 'Leaf document.'


class TestParseReferenceArg:
    def test_splits_on_walrus(self):
        assert parse_reference_arg('local:///a/b.yaml:=nodl://p/n') == ('local:///a/b.yaml', 'nodl://p/n')

    @pytest.mark.parametrize('bad', ['no-separator', ':=only-to', 'only-from:=', ''])
    def test_rejects_malformed(self, bad):
        with pytest.raises(RewriteError, match='expected FROM:=TO'):
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
        assert _load(output.read_text())['include'] == [{'ref': 'nodl://mypkg/leaf'}]

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
        assert 'unresolved local reference' in capsys.readouterr().err
