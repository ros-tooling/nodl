# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0

import argparse
from pathlib import Path
from unittest.mock import Mock

from nodl_schema import Difference, DiffReport
from ros2nodl.verb.conform import ConformVerb


def _args(**overrides):
    values = {
        'node_name': '/robot/controller',
        'file': Path('nodl/controller.nodl.yaml'),
        'timeout': 15.0,
        'ignore': [],
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def test_conform_passes_runtime_arguments(monkeypatch, capsys):
    monkeypatch.delenv('NODL_CONFORMANCE_IGNORE', raising=False)
    calls = []

    def assert_conforms(**kwargs):
        calls.append(kwargs)
        return DiffReport()

    import ros2nodl.conformance

    monkeypatch.setattr(ros2nodl.conformance, 'assert_conforms', assert_conforms)

    assert ConformVerb().main(args=_args(timeout=2.5, ignore=['publisher:/stats'])) == 0
    assert calls == [
        {
            'nodl_file': 'nodl/controller.nodl.yaml',
            'node_fqn': '/robot/controller',
            'timeout_sec': 2.5,
            'ignore': ['publisher:/stats'],
        }
    ]
    assert capsys.readouterr().out == '/robot/controller: conforms\n'


def test_conform_adds_the_environment_ignore_rules_before_the_arguments(monkeypatch):
    monkeypatch.setenv('NODL_CONFORMANCE_IGNORE', 'publisher:/a  parameter:b.*\n')
    calls = []

    import ros2nodl.conformance

    monkeypatch.setattr(ros2nodl.conformance, 'assert_conforms', lambda **kwargs: calls.append(kwargs) or DiffReport())

    assert ConformVerb().main(args=_args(ignore=['subscription:/c'])) == 0
    assert calls[0]['ignore'] == ['publisher:/a', 'parameter:b.*', 'subscription:/c']


def test_conform_reports_ignored_entities(monkeypatch, capsys):
    ignored = Difference('extra', 'publishers', '/stats', 'observed undeclared type')

    import ros2nodl.conformance

    monkeypatch.setattr(ros2nodl.conformance, 'assert_conforms', lambda **kwargs: DiffReport(ignored=[ignored]))

    assert ConformVerb().main(args=_args()) == 0
    assert capsys.readouterr().out == (
        "/robot/controller: conforms\n  ignored [extra] publishers '/stats': observed undeclared type\n"
    )


def test_conform_reports_all_differences(monkeypatch, capsys):
    message = "NoDL conformance failed for '/robot/controller':\n  [missing] publishers '/state': not observed"

    import ros2nodl.conformance

    monkeypatch.setattr(
        ros2nodl.conformance,
        'assert_conforms',
        Mock(side_effect=AssertionError(message)),
    )

    assert ConformVerb().main(args=_args()) == 1
    error = capsys.readouterr().err
    assert error.startswith('ros2 nodl conform: NoDL conformance failed')
    assert "[missing] publishers '/state': not observed" in error


def test_conform_reports_runtime_errors(monkeypatch, capsys):
    import ros2nodl.conformance

    monkeypatch.setattr(
        ros2nodl.conformance,
        'assert_conforms',
        Mock(side_effect=ValueError('failed to load document')),
    )

    assert ConformVerb().main(args=_args()) == 1
    assert capsys.readouterr().err == 'ros2 nodl conform: failed to load document\n'


def test_conform_arguments_are_required_and_typed():
    parser = argparse.ArgumentParser()
    ConformVerb().add_arguments(parser, 'ros2 nodl conform')

    args = parser.parse_args(['/robot/controller', '--file', 'node.nodl.yaml', '--timeout', '3.5'])

    assert args.node_name == '/robot/controller'
    assert args.file == Path('node.nodl.yaml')
    assert args.timeout == 3.5


def test_conform_ignore_is_repeatable_and_defaults_to_empty():
    parser = argparse.ArgumentParser()
    ConformVerb().add_arguments(parser, 'ros2 nodl conform')

    args = parser.parse_args([
        '/robot/controller',
        '--file',
        'node.nodl.yaml',
        '--ignore',
        'publisher:/a',
        '--ignore',
        'parameter:b.*',
    ])
    default = parser.parse_args(['/robot/controller', '--file', 'node.nodl.yaml'])

    assert args.ignore == ['publisher:/a', 'parameter:b.*']
    assert default.ignore == []
