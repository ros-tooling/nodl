# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for the ``ros2 nodl diff`` verb."""

import argparse
from pathlib import Path

from ros2nodl.verb.diff import DiffVerb


def _args(expected: Path, actual: Path, *, node_name: str = '/node') -> argparse.Namespace:
    return argparse.Namespace(expected=expected, actual=actual, node_name=node_name)


def _write(path: Path, content: str = 'nodl_version: 2\n') -> Path:
    path.write_text(content)
    return path


def test_equal_documents_exit_zero_without_output(tmp_path, capsys):
    expected = _write(tmp_path / 'expected.yaml')
    actual = _write(tmp_path / 'actual.yaml')

    assert DiffVerb().main(args=_args(expected, actual)) == 0
    assert capsys.readouterr().out == ''


def test_differences_are_printed_and_exit_one(tmp_path, capsys):
    expected = _write(
        tmp_path / 'expected.yaml',
        'nodl_version: 2\n'
        'publishers:\n'
        '  - name: status\n'
        '    type: std_msgs/msg/String\n'
        '    qos: {history: KEEP_LAST, depth: 10, reliability: RELIABLE}\n',
    )
    actual = _write(tmp_path / 'actual.yaml')

    assert DiffVerb().main(args=_args(expected, actual, node_name='/robot/controller')) == 1
    assert capsys.readouterr().out == (
        "[missing] publishers '/robot/status': expected type 'std_msgs/msg/String' was not observed\n"
    )


def test_load_errors_are_reported_and_exit_two(tmp_path, capsys):
    missing = tmp_path / 'missing.yaml'
    actual = _write(tmp_path / 'actual.yaml')

    assert DiffVerb().main(args=_args(missing, actual)) == 2
    assert capsys.readouterr().err.startswith('ros2 nodl diff: ')


def test_documents_are_resolved_before_comparison(tmp_path, capsys):
    _write(
        tmp_path / 'shared.yaml',
        'nodl_version: 2\n'
        'publishers:\n'
        '  - name: status\n'
        '    type: std_msgs/msg/String\n'
        '    qos: {history: KEEP_LAST, depth: 10, reliability: RELIABLE}\n',
    )
    expected = _write(
        tmp_path / 'expected.yaml',
        'nodl_version: 2\ninclude:\n  - ref: local://shared.yaml\n',
    )
    actual = _write(
        tmp_path / 'actual.yaml',
        'nodl_version: 2\n'
        'publishers:\n'
        '  - name: status\n'
        '    type: std_msgs/msg/String\n'
        '    qos: {history: KEEP_LAST, depth: 10, reliability: RELIABLE}\n',
    )

    assert DiffVerb().main(args=_args(expected, actual)) == 0
    assert capsys.readouterr().out == ''


def test_unresolved_include_is_an_error(tmp_path, capsys):
    expected = _write(
        tmp_path / 'expected.yaml',
        'nodl_version: 2\ninclude:\n  - ref: nodl://no_such_package/no_such_node\n',
    )
    actual = _write(tmp_path / 'actual.yaml')

    assert DiffVerb().main(args=_args(expected, actual)) == 2
    assert 'ros2 nodl diff:' in capsys.readouterr().err


def test_arguments_are_required_and_typed():
    parser = argparse.ArgumentParser()
    DiffVerb().add_arguments(parser, 'ros2 nodl diff')

    args = parser.parse_args(['expected.yaml', 'actual.yaml', '--node-name', '/robot/controller'])

    assert args.expected == Path('expected.yaml')
    assert args.actual == Path('actual.yaml')
    assert args.node_name == '/robot/controller'
