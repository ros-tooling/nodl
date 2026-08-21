# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for the NoDL rclpy generator."""

import ast
from pathlib import Path

import pytest

from nodl_generator_py import generator
from nodl_schema.models import Durability, History, Liveliness, QosProfile, Reliability

_FIXTURES = Path(__file__).parent / 'fixtures'
_TEMPLATES = Path(__file__).parents[1] / 'templates'


@pytest.mark.parametrize(
    'name,expected',
    [
        ('my_node', 'MyNode'),
        ('pubsub_node', 'PubsubNode'),
        ('foo_bar_baz', 'FooBarBaz'),
    ],
)
def test_snake_to_pascal(name, expected):
    assert generator._snake_to_pascal(name) == expected


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
    assert generator._topic_to_identifier(topic) == expected


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
    ],
)
def test_ros_type_conversion(ros_type, kind, expected_import, expected_symbol):
    assert generator._ros_type_to_import(ros_type, kind) == expected_import
    assert generator._ros_type_to_py(ros_type, kind) == expected_symbol


def test_ros_type_kind_must_match_endpoint():
    with pytest.raises(ValueError, match='expected msg'):
        generator._ros_type_to_py('example_interfaces/srv/AddTwoInts', 'msg')


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
    rendered = generator._qos_to_py(qos)
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


@pytest.mark.parametrize(
    'name,lifecycle,snippets',
    [
        (
            'pubsub_node',
            False,
            [
                'class PubsubNodeBase(Node, metaclass=abc.ABCMeta):',
                'self.pub_echo_out = self.create_publisher(',
                'std_msgs.msg.String',
                'def on_echo_in(self, msg):',
            ],
        ),
        (
            'service_node',
            False,
            [
                'def on_add(self, request, response):',
                'self.cli_delegate_add = self.create_client(',
                'example_interfaces.srv.AddTwoInts',
                'qos_profile=rclpy.qos.QoSProfile(',
            ],
        ),
        (
            'action_node',
            False,
            [
                'self.action_server_fibonacci = rclpy.action.ActionServer(',
                'def execute_fibonacci(self, goal_handle):',
                'self.action_client_delegate_fibonacci = rclpy.action.ActionClient(',
            ],
        ),
        (
            'params_node',
            False,
            [
                'from . import params_node_params',
                'self.param_listener_ = params_node_params.ParamListener(self)',
            ],
        ),
        (
            'lifecycle_pubsub_node',
            True,
            [
                'class LifecyclePubsubNodeBase(LifecycleNode, metaclass=abc.ABCMeta):',
                'self.pub_lc_echo_out = self.create_lifecycle_publisher(',
            ],
        ),
    ],
)
def test_generate(name, lifecycle, snippets, monkeypatch, tmp_path):
    monkeypatch.setattr(
        generator,
        '_generate_params_module',
        lambda output, _: output.write_text('', encoding='utf-8'),
    )
    output = generator.generate(
        _FIXTURES / f'{name}.nodl.yaml',
        tmp_path,
        name,
        _TEMPLATES,
        lifecycle=lifecycle,
    )
    rendered = output.read_text(encoding='utf-8')
    tree = ast.parse(rendered)
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name.split('.')[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module.split('.')[0])
    assert imports.isdisjoint({'nodl', 'nodl_schema', 'nodl_generator_py'})
    for snippet in snippets:
        assert snippet in rendered
    if name == 'params_node':
        assert '!!python' not in (tmp_path / 'params_node_params.yaml').read_text()
