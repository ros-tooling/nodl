# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Check that the generated modules import as ``<package>.generated.<target>`` and behave as generated nodes."""

import importlib
import time
from pathlib import Path

import pytest
from conftest import PACKAGE, SOURCE_ROOT
from rclpy.executors import SingleThreadedExecutor
from rclpy.lifecycle import LifecycleNode
from rclpy.node import Node
from std_msgs.msg import String

from test_nodl_generators_ament_python.composed_node import ComposedNode
from test_nodl_generators_ament_python.echo_node import EchoNode
from test_nodl_generators_ament_python.lifecycle_node import LifecycleStatusNode

TARGETS = [
    'echo_node_base',
    'unindexed_echo_node_base',
    'lifecycle_node_base',
    'status_mixin_base',
    'composed_node_base',
]


def _spin_until(executor, predicate, timeout=5.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline and not predicate():
        executor.spin_once(timeout_sec=0.05)
    return predicate()


@pytest.mark.parametrize('target', TARGETS)
def test_generated_module_imports_from_the_built_package(target):
    module = importlib.import_module(f'{PACKAGE}.generated.{target}')

    assert SOURCE_ROOT not in Path(module.__file__).resolve().parents


def test_parameter_module_is_generated_for_a_document_with_parameters():
    module = importlib.import_module(f'{PACKAGE}.generated.echo_node_base_parameters')

    assert hasattr(module, 'echo_node')


def test_generated_code_is_not_written_to_the_source_tree():
    assert not (SOURCE_ROOT / PACKAGE / 'generated').exists()
    assert not list(SOURCE_ROOT.rglob('*_parameters.yaml'))


def test_echo_node_echoes_with_its_typed_parameter(ros_context):
    node = EchoNode()
    harness = Node('test_harness')
    received = []
    harness.create_subscription(String, '/echo_out', lambda msg: received.append(msg.data), 10)
    publisher = harness.create_publisher(String, '/echo_in', 10)
    executor = SingleThreadedExecutor()
    executor.add_node(node)
    executor.add_node(harness)
    try:
        assert 'echo_node' == node.get_name()
        assert _spin_until(executor, lambda: publisher.get_subscription_count() > 0)

        publisher.publish(String(data='ping'))

        assert _spin_until(executor, lambda: bool(received))
        assert ['hello: ping'] == received
    finally:
        executor.shutdown()
        node.destroy_node()
        harness.destroy_node()


def test_lifecycle_document_generates_a_lifecycle_node():
    assert issubclass(LifecycleStatusNode, LifecycleNode)


def test_included_document_contributes_its_entities(ros_context):
    node = ComposedNode()
    try:
        assert hasattr(node, 'pub_status')
        assert hasattr(node, 'sub_composed_in')
    finally:
        node.destroy_node()
