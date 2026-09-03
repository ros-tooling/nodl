# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for the NoDL rclpy generator."""

import ast
from pathlib import Path

import pytest

from nodl_generator_py import generate_parameter_yaml, generate_python
from nodl_generator_py.cli import main
from nodl_generator_py.generator import (
    _qos_to_py,
    _ros_type_to_import,
    _ros_type_to_py,
    _snake_to_pascal,
    _topic_to_identifier,
)
from nodl_schema import load_nodl
from nodl_schema.models import Durability, History, Liveliness, NodlDocument, QosProfile, Reference, Reliability

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
    'topic,expected',
    [
        ('/scan', 'scan'),
        ('/echo_out', 'echo_out'),
        ('/my/long/topic', 'my_long_topic'),
        ('relative', 'relative'),
    ],
)
def test_topic_to_identifier(topic, expected):
    assert _topic_to_identifier(topic) == expected


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


def test_generate_python():
    doc = load_nodl(_FIXTURES / 'interfaces_node.nodl.yaml', resolve=False)

    generated = generate_python(doc, 'interfaces_node')

    tree = ast.parse(generated)
    imports = {
        alias.name.split('.')[0] for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names
    }
    imports.update(
        node.module.split('.')[0] for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module
    )
    assert imports.isdisjoint({'nodl', 'nodl_schema', 'nodl_generator_py'})
    for expected in (
        'from . import interfaces_node_params',
        'class InterfacesNodeBase(Node, metaclass=abc.ABCMeta):',
        'self.param_listener_ = interfaces_node_params.interfaces_node.ParamListener(self)',
        'self.pub_echo_out = self.create_publisher(',
        'def on_echo_in(self, msg):',
        'self.srv_add = self.create_service(',
        'def on_add(self, request, response):',
        'self.cli_delegate_add = self.create_client(',
        'self.action_server_fibonacci = rclpy.action.ActionServer(',
        'def execute_fibonacci(self, goal_handle):',
        'self.action_client_delegate_fibonacci = rclpy.action.ActionClient(',
    ):
        assert expected in generated

    parameters_yaml = generate_parameter_yaml(doc, 'interfaces_node')
    assert 'greeting:' in parameters_yaml
    assert '!!python' not in parameters_yaml


def test_generate_python_rejects_includes():
    doc = NodlDocument(include=[Reference(ref='nodl://example/base')])

    with pytest.raises(NotImplementedError, match='does not yet support include composition'):
        generate_python(doc, 'including_node')


def test_generate_python_rejects_invalid_target_name():
    with pytest.raises(ValueError, match='valid Python identifier'):
        generate_python(NodlDocument(), 'invalid-name')


def test_cli_writes_generated_module(tmp_path):
    result = main([
        '--nodl-file',
        str(_FIXTURES / 'interfaces_node.nodl.yaml'),
        '--output-dir',
        str(tmp_path),
        '--target-name',
        'interfaces_node',
    ])

    assert result == 0
    assert (tmp_path / 'interfaces_node.py').is_file()
    assert (tmp_path / 'interfaces_node_params.py').is_file()
