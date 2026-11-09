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
from nodl_generator_py.models import CodegenPython, Role
from nodl_schema import load_nodl, parse_nodl
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
        'def on_echo_in(self, msg: std_msgs.msg.String) -> None:',
        'self.srv_add = self.create_service(',
        'def on_add(self, request: example_interfaces.srv.AddTwoInts.Request, response: example_interfaces.srv.AddTwoInts.Response) -> example_interfaces.srv.AddTwoInts.Response:',
        'self.cli_delegate_add = self.create_client(',
        'self.action_srv_fibonacci = rclpy.action.ActionServer(',
        'goal_callback=self.on_fibonacci_goal,',
        'cancel_callback=self.on_fibonacci_cancel,',
        'def on_fibonacci_goal(self, goal_request: example_interfaces.action.Fibonacci.Goal) -> rclpy.action.GoalResponse:',
        'def on_fibonacci_cancel(self, goal_handle: rclpy.action.server.ServerGoalHandle) -> rclpy.action.CancelResponse:',
        'def execute_fibonacci(self, goal_handle: rclpy.action.server.ServerGoalHandle) -> example_interfaces.action.Fibonacci.Result:',
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


_ACTIVATION_GATED_BASE = CodegenPython(
    role=Role.BASE_CLASS,
    module='nodl_runtime_py.lifecycle',
    activation_gated=True,
    **{'class': 'LifecycleNode'},
)


def test_render_python_activates_only_subscriptions_and_services_of_an_activation_gated_base():
    doc = load_nodl(_FIXTURES / 'interfaces_node.nodl.yaml', resolve=False)

    generated = _render_python(doc, 'interfaces_node_base', _ACTIVATION_GATED_BASE)

    ast.parse(generated)
    for expected in (
        'from nodl_runtime_py.active_only import create_active_only_service',
        'from nodl_runtime_py.active_only import active_only_subscription_callback',
        'active_only_subscription_callback(self.activation_gate, self.on_echo_in),',
        'self.srv_add = create_active_only_service(\n            self,\n            self.activation_gate,\n            example_interfaces.srv.AddTwoInts,',
    ):
        assert expected in generated
    assert 'self.create_service(' not in generated
    assert '            self.on_echo_in,\n' not in generated


def test_render_python_wraps_clients_of_an_activation_gated_base():
    doc = load_nodl(_FIXTURES / 'interfaces_node.nodl.yaml', resolve=False)

    generated = _render_python(doc, 'interfaces_node_base', _ACTIVATION_GATED_BASE)

    ast.parse(generated)
    for expected in (
        'from nodl_runtime_py.active_only import ActiveOnlyActionClient',
        'from nodl_runtime_py.active_only import ActiveOnlyClient',
        "self.cli_delegate_add = ActiveOnlyClient(\n            self.activation_gate,\n            self.create_client(\n                example_interfaces.srv.AddTwoInts,\n                '/delegate_add',\n                qos_profile=",
        'self.action_cli_delegate_fibonacci = ActiveOnlyActionClient(\n            self.activation_gate,\n            rclpy.action.ActionClient(\n                self,\n                example_interfaces.action.Fibonacci,',
    ):
        assert expected in generated
    assert '= self.create_client(' not in generated
    assert '= rclpy.action.ActionClient(' not in generated


def test_render_python_imports_only_the_client_wrappers_it_uses():
    doc = parse_nodl(
        """
nodl_version: 2
action_clients:
  - name: /delegate_fibonacci
    type: example_interfaces/action/Fibonacci
"""
    )

    generated = _render_python(doc, 'action_client_node_base', _ACTIVATION_GATED_BASE)

    assert 'from nodl_runtime_py.active_only import ActiveOnlyActionClient\n' in generated
    assert 'ActiveOnlyClient' not in generated


def test_render_python_leaves_a_non_activation_gated_base_unchanged():
    doc = load_nodl(_FIXTURES / 'interfaces_node.nodl.yaml', resolve=False)

    generated = _render_python(doc, 'interfaces_node_base')

    assert 'nodl_runtime_py' not in generated
    assert 'activation_gate' not in generated
    assert '            self.on_echo_in,\n' in generated
    assert 'self.srv_add = self.create_service(' in generated
    assert 'self.cli_delegate_add = self.create_client(' in generated
    assert 'self.action_cli_delegate_fibonacci = rclpy.action.ActionClient(' in generated


def test_generate_parameter_yaml_preserves_integer_validation_values():
    doc = parse_nodl(
        """
        nodl_version: 2
        parameters:
          count:
            type: int
            default_value: 3
            validation:
              bounds<>: [0, 10]
        """
    )

    parameters_yaml = generate_parameter_yaml(doc, 'test_node_base')
    assert parameters_yaml is not None
    data = yaml.safe_load(parameters_yaml)
    parameter = data['test_node']['count']

    assert parameter['default_value'] == 3
    assert type(parameter['default_value']) is int
    assert parameter['validation']['bounds<>'] == [0, 10]
    assert [type(value) for value in parameter['validation']['bounds<>']] == [int, int]


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
