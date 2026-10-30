# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Tests for the executable generator."""

import ast
import os
import stat

import pytest

from nodl_generator_py.executable import executable_source, main


def _run_node_call(source: str) -> ast.Call:
    exit_call = ast.parse(source).body[-1].value
    return exit_call.args[0]


def test_source_runs_the_class_with_run_node():
    source = executable_source('my_pkg.my_module:MyNode')

    assert source == (
        '#!/usr/bin/env python3\n'
        'import sys\n'
        '\n'
        'from nodl_runtime_py import run_node\n'
        'from my_pkg.my_module import MyNode\n'
        '\n'
        'sys.exit(run_node(MyNode))\n'
    )


def test_source_passes_the_executor_class():
    source = executable_source('my_pkg:MyNode', 'rclpy.executors:MultiThreadedExecutor')

    assert source == (
        '#!/usr/bin/env python3\n'
        'import sys\n'
        '\n'
        'from nodl_runtime_py import run_node\n'
        'from my_pkg import MyNode\n'
        'from rclpy.executors import MultiThreadedExecutor\n'
        '\n'
        'sys.exit(run_node(MyNode, executor_class=MultiThreadedExecutor))\n'
    )


@pytest.mark.parametrize('executor', [None, 'rclpy.executors:MultiThreadedExecutor'])
def test_source_is_valid_python(executor):
    source = executable_source('my_pkg:MyNode', executor)
    compile(source, '<generated>', 'exec')
    call = _run_node_call(source)

    assert call.func.id == 'run_node'
    assert [keyword.arg for keyword in call.keywords] == ([] if executor is None else ['executor_class'])


@pytest.mark.parametrize(
    'reference',
    [
        '',
        'my_pkg',
        'my_pkg:',
        ':MyNode',
        'my_pkg:My.Node',
        'my_pkg.:MyNode',
        'my-pkg:MyNode',
        'my_pkg:My Node',
        'my_pkg:1Node',
        'my_pkg:class',
        'if.my_pkg:MyNode',
        'my_pkg.None:MyNode',
        'my_pkg:None',
    ],
)
def test_malformed_target_is_rejected(reference):
    with pytest.raises(ValueError, match='is not in the form'):
        executable_source(reference)


@pytest.mark.parametrize(
    'reference', ['', 'rclpy.executors', 'rclpy.executors:', ':Executor', 'a b:Executor', 'a:class', 'a.if:B', 'a:None']
)
def test_malformed_executor_is_rejected(reference):
    with pytest.raises(ValueError, match=r"Executor '.*' is not in the form"):
        executable_source('my_pkg:MyNode', reference)


@pytest.mark.parametrize(
    ('target', 'executor'),
    [('a:Same', 'b:Same'), ('a:sys', None), ('a:run_node', None), ('a:Node', 'b:sys')],
)
def test_clashing_class_names_are_rejected(target, executor):
    with pytest.raises(ValueError, match='must be distinct'):
        executable_source(target, executor)


def test_cli_prints_the_source(capsys):
    assert 0 == main(['my_pkg:MyNode'])

    assert capsys.readouterr().out == executable_source('my_pkg:MyNode')


def test_cli_writes_an_executable_file(tmp_path):
    output = tmp_path / 'bin' / 'my_node'

    assert 0 == main(['my_pkg:MyNode', '--executor', 'rclpy.executors:MultiThreadedExecutor', '--output', str(output)])

    assert output.read_text() == executable_source('my_pkg:MyNode', 'rclpy.executors:MultiThreadedExecutor')
    assert 0o755 == stat.S_IMODE(os.stat(output).st_mode)


def test_cli_reports_a_malformed_reference(tmp_path, capsys):
    output = tmp_path / 'my_node'

    assert 1 == main(['my_pkg', '--output', str(output)])

    assert "Node target 'my_pkg' is not in the form" in capsys.readouterr().err
    assert not output.exists()
