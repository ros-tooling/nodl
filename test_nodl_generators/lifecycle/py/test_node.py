# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Runtime test for the generated entities of a lifecycle node in each state."""

import time

import pytest
import rclpy
from example_interfaces.srv import AddTwoInts
from node_impl import GeneratedLifecycleNode
from rclpy.executors import SingleThreadedExecutor
from rclpy.lifecycle import LifecycleNode, LifecyclePublisher, TransitionCallbackReturn
from rclpy.node import Node
from std_msgs.msg import String


@pytest.fixture
def ros_context():
    rclpy.init()
    try:
        yield
    finally:
        rclpy.shutdown()


def _spin_until(executor, predicate, timeout=10.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline and not predicate():
        executor.spin_once(timeout_sec=0.05)
    return predicate()


def test_generated_publisher_follows_lifecycle_transitions(ros_context):
    node = GeneratedLifecycleNode()
    harness = Node('lifecycle_test_harness')
    received = []
    harness.create_subscription(String, '/lifecycle_status', lambda msg: received.append(msg.data), 10)

    executor = SingleThreadedExecutor()
    executor.add_node(node)
    executor.add_node(harness)
    try:
        assert isinstance(node, LifecycleNode)
        assert isinstance(node.pub_lifecycle_status, LifecyclePublisher)
        assert _spin_until(executor, lambda: node.pub_lifecycle_status.get_subscription_count() > 0)

        node.pub_lifecycle_status.publish(String(data='inactive'))
        assert not _spin_until(executor, lambda: bool(received), timeout=0.2)

        assert node.trigger_configure() == TransitionCallbackReturn.SUCCESS
        assert node.trigger_activate() == TransitionCallbackReturn.SUCCESS
        assert node.activate_count == 1
        node.pub_lifecycle_status.publish(String(data='active'))
        assert _spin_until(executor, lambda: received == ['active'])

        assert node.trigger_deactivate() == TransitionCallbackReturn.SUCCESS
        node.pub_lifecycle_status.publish(String(data='inactive-again'))
        assert not _spin_until(executor, lambda: len(received) > 1, timeout=0.2)
    finally:
        executor.shutdown()
        node.destroy_node()
        harness.destroy_node()


@pytest.fixture
def lifecycle_setup(ros_context):
    node = GeneratedLifecycleNode()
    harness = Node('lifecycle_gate_harness')
    executor = SingleThreadedExecutor()
    executor.add_node(node)
    executor.add_node(harness)
    command_pub = harness.create_publisher(String, '/lifecycle_command', 10)
    add_client = harness.create_client(AddTwoInts, '/lifecycle_add')
    try:
        yield node, executor, command_pub, add_client
    finally:
        executor.shutdown()
        node.destroy_node()
        harness.destroy_node()


def _send_command(executor, command_pub, data):
    assert _spin_until(executor, lambda: command_pub.get_subscription_count() > 0)
    command_pub.publish(String(data=data))


def _call_add(executor, add_client, a, b):
    assert _spin_until(executor, add_client.service_is_ready)
    return add_client.call_async(AddTwoInts.Request(a=a, b=b))


def test_generated_subscription_delivers_only_while_active(lifecycle_setup):
    node, executor, command_pub, _ = lifecycle_setup

    _send_command(executor, command_pub, 'unconfigured')
    assert not _spin_until(executor, lambda: bool(node.commands), timeout=0.3)

    node.trigger_configure()
    _send_command(executor, command_pub, 'inactive')
    assert not _spin_until(executor, lambda: bool(node.commands), timeout=0.3)

    node.trigger_activate()
    _send_command(executor, command_pub, 'active')
    assert _spin_until(executor, lambda: ['active'] == node.commands)

    node.trigger_deactivate()
    _send_command(executor, command_pub, 'inactive-again')
    assert not _spin_until(executor, lambda: len(node.commands) > 1, timeout=0.3)


def test_generated_service_responds_only_while_active(lifecycle_setup):
    node, executor, _, add_client = lifecycle_setup

    unconfigured = _call_add(executor, add_client, 1, 2)
    assert not _spin_until(executor, unconfigured.done, timeout=0.3)

    node.trigger_configure()
    inactive = _call_add(executor, add_client, 1, 2)
    assert not _spin_until(executor, inactive.done, timeout=0.3)

    node.trigger_activate()
    active = _call_add(executor, add_client, 3, 4)
    assert _spin_until(executor, active.done)
    assert 7 == active.result().sum

    node.trigger_deactivate()
    inactive_again = _call_add(executor, add_client, 5, 6)
    assert not _spin_until(executor, inactive_again.done, timeout=0.3)
