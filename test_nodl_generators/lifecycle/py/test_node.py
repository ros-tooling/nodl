# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Runtime test for generated managed lifecycle publishers."""

import time

import pytest
import rclpy
from node_impl import GeneratedLifecycleNode
from rclpy.executors import SingleThreadedExecutor
from rclpy.lifecycle import LifecycleNode, LifecyclePublisher, TransitionCallbackReturn
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from std_msgs.msg import String

from nodl_runtime_py.lifecycle import LifecycleNode as NodlLifecycleNode


@pytest.fixture
def ros_context():
    rclpy.init()
    try:
        yield
    finally:
        rclpy.shutdown()


def _spin_until(executor, predicate, timeout=2.0):
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
        assert isinstance(node, NodlLifecycleNode)
        assert isinstance(node.pub_lifecycle_status, LifecyclePublisher)
        assert _spin_until(executor, lambda: node.pub_lifecycle_status.get_subscription_count() > 0)

        node.pub_lifecycle_status.publish(String(data='inactive'))
        assert not _spin_until(executor, lambda: bool(received), timeout=0.2)

        assert node.trigger_configure() == TransitionCallbackReturn.SUCCESS
        assert node.trigger_activate() == TransitionCallbackReturn.SUCCESS
        assert node.activations == 1
        node.pub_lifecycle_status.publish(String(data='active'))
        assert _spin_until(executor, lambda: received == ['active'])

        assert node.trigger_deactivate() == TransitionCallbackReturn.SUCCESS
        node.pub_lifecycle_status.publish(String(data='inactive-again'))
        assert not _spin_until(executor, lambda: len(received) > 1, timeout=0.2)
    finally:
        executor.shutdown()
        node.destroy_node()
        harness.destroy_node()


def _subscribers(harness, topic):
    return [info.node_name for info in harness.get_subscriptions_info_by_topic(topic)]


@pytest.fixture
def lifecycle_rig(ros_context):
    node = GeneratedLifecycleNode()
    harness = Node('lifecycle_test_harness')
    executor = SingleThreadedExecutor()
    executor.add_node(node)
    executor.add_node(harness)
    try:
        yield node, harness, executor
    finally:
        executor.shutdown()
        node.destroy_node()
        harness.destroy_node()


def test_generated_subscriptions_are_in_the_graph_only_while_active(lifecycle_rig):
    node, harness, executor = lifecycle_rig

    def listed(topic):
        return node.get_name() in _subscribers(harness, topic)

    def settle(topic, present):
        return _spin_until(executor, lambda: listed(topic) is present)

    assert not _spin_until(executor, lambda: listed('/cmd'), timeout=0.3)
    assert node.trigger_configure() == TransitionCallbackReturn.SUCCESS
    assert not _spin_until(executor, lambda: listed('/cmd') or listed('/latched'), timeout=0.3)

    assert node.trigger_activate() == TransitionCallbackReturn.SUCCESS
    assert settle('/cmd', True)
    assert settle('/latched', True)

    assert node.trigger_deactivate() == TransitionCallbackReturn.SUCCESS
    assert settle('/cmd', False)
    assert settle('/latched', False)

    assert node.trigger_activate() == TransitionCallbackReturn.SUCCESS
    assert settle('/cmd', True)
    assert settle('/latched', True)


def test_latched_sample_from_before_configure_arrives_after_activation(lifecycle_rig):
    node, harness, executor = lifecycle_rig
    latched = harness.create_publisher(
        String,
        '/latched',
        QoSProfile(
            depth=1,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
        ),
    )
    latched.publish(String(data='latched'))

    assert not _spin_until(executor, lambda: bool(node.latched_received), timeout=0.3)
    assert node.trigger_configure() == TransitionCallbackReturn.SUCCESS
    assert not _spin_until(executor, lambda: bool(node.latched_received), timeout=0.3)

    assert node.trigger_activate() == TransitionCallbackReturn.SUCCESS
    assert _spin_until(executor, lambda: node.latched_received == ['latched'])

    # A new subscription is created on every activation, so the latched sample is delivered again.
    assert node.trigger_deactivate() == TransitionCallbackReturn.SUCCESS
    assert not _spin_until(executor, lambda: len(node.latched_received) > 1, timeout=0.3)
    assert node.trigger_activate() == TransitionCallbackReturn.SUCCESS
    assert _spin_until(executor, lambda: len(node.latched_received) == 2)


def test_generated_subscription_receives_only_while_active(lifecycle_rig):
    node, harness, executor = lifecycle_rig
    cmd = harness.create_publisher(String, '/cmd', QoSProfile(depth=1, reliability=ReliabilityPolicy.BEST_EFFORT))

    assert node.trigger_configure() == TransitionCallbackReturn.SUCCESS
    cmd.publish(String(data='configured'))
    assert not _spin_until(executor, lambda: bool(node.cmd_received), timeout=0.3)

    assert node.trigger_activate() == TransitionCallbackReturn.SUCCESS
    assert _spin_until(executor, lambda: cmd.get_subscription_count() > 0)
    cmd.publish(String(data='active'))
    assert _spin_until(executor, lambda: node.cmd_received == ['active'])

    assert node.trigger_deactivate() == TransitionCallbackReturn.SUCCESS
    assert _spin_until(executor, lambda: cmd.get_subscription_count() == 0)
    cmd.publish(String(data='inactive'))
    assert not _spin_until(executor, lambda: len(node.cmd_received) > 1, timeout=0.3)
