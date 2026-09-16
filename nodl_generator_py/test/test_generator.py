# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for the NoDL rclpy generator."""

import ast
from pathlib import Path

import pytest
import yaml

from nodl_generator_py import generate_parameter_yaml
from nodl_generator_py.cli import main
from nodl_generator_py.generator import (
    _qos_to_py,
    _render_python,
    _ros_type_to_import,
    _ros_type_to_py,
    _snake_to_pascal,
    _target_to_node_name,
)
from nodl_schema import load_nodl
from nodl_schema.models import (
    Durability,
    History,
    Liveliness,
    NodlDocument,
    QosProfile,
    Reference,
    Reliability,
    TopicEndpoint,
)

_FIXTURES = Path(__file__).parent / 'fixtures'


@pytest.mark.parametrize(
    'name,expected',
    [
        ('my_node', 'MyNode'),
        ('pubsub_node', 'PubsubNode'),
        ('foo_bar_baz', 'FooBarBaz'),
    ],
)
def test_snake_to_pascal(name, expected):
    assert _snake_to_pascal(name) == expected


@pytest.mark.parametrize(
    'target,expected',
    [
        ('my_node_base', 'my_node'),
        ('my_node', 'my_node'),
    ],
)
def test_target_to_node_name(target, expected):
    assert _target_to_node_name(target) == expected


@pytest.mark.parametrize(
    'ros_type,kind,expected_import,expected_symbol',
    [
        ('std_msgs/msg/String', 'msg', 'import std_msgs.msg', 'std_msgs.msg.String'),
        ('std_msgs/String', 'msg', 'import std_msgs.msg', 'std_msgs.msg.String'),
        (
            'example_interfaces/srv/AddTwoInts',
            'srv',
            'import example_interfaces.srv',
            'example_interfaces.srv.AddTwoInts',
        ),
        (
            'example_interfaces/action/Fibonacci',
            'action',
            'import example_interfaces.action',
            'example_interfaces.action.Fibonacci',
        ),
    ],
)
def test_ros_type_conversion(ros_type, kind, expected_import, expected_symbol):
    assert _ros_type_to_import(ros_type, kind) == expected_import
    assert _ros_type_to_py(ros_type, kind) == expected_symbol


def test_ros_type_kind_must_match_endpoint():
    with pytest.raises(ValueError, match='expected msg'):
        _ros_type_to_py('example_interfaces/srv/AddTwoInts', 'msg')


def test_qos_to_py():
    qos = QosProfile(
        history=History.KEEP_LAST,
        depth=5,
        reliability=Reliability.BEST_EFFORT,
        durability=Durability.TRANSIENT_LOCAL,
        deadline_ns=1_000,
        liveliness=Liveliness.MANUAL_BY_TOPIC,
        liveliness_lease_duration_ns=2_000,
    )

    rendered = _qos_to_py(qos)

    for expected in (
        'rclpy.qos.HistoryPolicy.KEEP_LAST',
        'depth=5',
        'rclpy.qos.ReliabilityPolicy.BEST_EFFORT',
        'rclpy.qos.DurabilityPolicy.TRANSIENT_LOCAL',
        'deadline=Duration(nanoseconds=1000)',
        'rclpy.qos.LivelinessPolicy.MANUAL_BY_TOPIC',
        'liveliness_lease_duration=Duration(nanoseconds=2000)',
    ):
        assert expected in rendered


def test_zero_qos_durations_use_unlimited_defaults():
    qos = QosProfile(
        history=History.KEEP_LAST,
        depth=1,
        reliability=Reliability.RELIABLE,
        deadline_ns=0,
        lifespan_ns=0,
        liveliness_lease_duration_ns=0,
    )
    doc = NodlDocument(publishers=[TopicEndpoint(name='status', type='std_msgs/msg/String', qos=qos)])

    assert 'Duration' not in _render_python(doc, 'example_node')


def test_render_python():
    doc = load_nodl(_FIXTURES / 'interfaces_node.nodl.yaml', resolve=False)

    generated = _render_python(doc, 'interfaces_node_base')

    tree = ast.parse(generated)
    imports = {
        alias.name.split('.')[0] for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names
    }
    imports.update(
        node.module.split('.')[0] for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module
    )
    assert imports.isdisjoint({'nodl', 'nodl_schema', 'nodl_generator_py'})
    for expected in (
        'from . import interfaces_node_base_parameters',
        'class InterfacesNodeBase(Node, metaclass=abc.ABCMeta):',
        "super().__init__('interfaces_node', **kwargs)",
        'self.param_listener_ = interfaces_node_base_parameters.interfaces_node.ParamListener(self)',
        'self.pub_echo_out = self.create_publisher(',
        'def on_echo_in(self, msg):',
        'self.srv_add = self.create_service(',
        'def on_add(self, request, response):',
        'self.cli_delegate_add = self.create_client(',
        'self.action_srv_fibonacci = rclpy.action.ActionServer(',
        'goal_callback=self.on_fibonacci_goal,',
        'cancel_callback=self.on_fibonacci_cancel,',
        'def on_fibonacci_goal(self, goal_request):',
        'def on_fibonacci_cancel(self, goal_handle):',
        'def execute_fibonacci(self, goal_handle):',
        'self.action_cli_delegate_fibonacci = rclpy.action.ActionClient(',
    ):
        assert expected in generated

    parameters_yaml = generate_parameter_yaml(doc, 'interfaces_node_base')
    assert parameters_yaml.startswith('interfaces_node:')
    assert 'greeting:' in parameters_yaml
    assert '!!python' not in parameters_yaml
    parameters = yaml.safe_load(parameters_yaml)['interfaces_node']
    assert 'colour.r' not in parameters
    assert parameters['colour']['r']['default_value'] == 0.8
    assert parameters['colour']['g']['default_value'] == 0.4


def test_render_python_rejects_unresolved_includes():
    doc = NodlDocument(include=[Reference(ref='nodl://example/base')])

    with pytest.raises(NotImplementedError, match='requires a resolved, flat'):
        _render_python(doc, 'including_node')


def test_render_python_rejects_invalid_target_name():
    with pytest.raises(ValueError, match='valid Python identifier'):
        _render_python(NodlDocument(), 'invalid-name')


def test_cli_writes_generated_module(tmp_path):
    result = main([
        '--nodl-file',
        str(_FIXTURES / 'interfaces_node.nodl.yaml'),
        '--output-dir',
        str(tmp_path),
        '--target-name',
        'interfaces_node_base',
    ])

    assert result == 0
    assert (tmp_path / 'interfaces_node_base.py').is_file()
    parameters_module = tmp_path / 'interfaces_node_base_parameters.py'
    assert parameters_module.is_file()
    ast.parse(parameters_module.read_text(encoding='utf-8'))
    doc = load_nodl(_FIXTURES / 'interfaces_node.nodl.yaml', resolve=False)
    assert (tmp_path / 'interfaces_node_base.py').read_text(encoding='utf-8') == _render_python(
        doc,
        'interfaces_node_base',
    )


def test_cli_writes_transitive_cmake_dependencies(tmp_path):
    included = tmp_path / 'included.nodl.yaml'
    included.write_text('nodl_version: 2\n', encoding='utf-8')
    root = tmp_path / 'root.nodl.yaml'
    root.write_text(
        'nodl_version: 2\ninclude:\n  - ref: local://included.nodl.yaml\n',
        encoding='utf-8',
    )

    result = main([
        '--nodl-file',
        str(root),
        '--output-dir',
        str(tmp_path),
        '--target-name',
        'example_base',
        '--cmake-deps',
    ])

    assert result == 0
    deps = (tmp_path / 'example_base_deps.cmake').read_text(encoding='utf-8')
    assert str(root.resolve()) in deps
    assert str(included.resolve()) in deps
