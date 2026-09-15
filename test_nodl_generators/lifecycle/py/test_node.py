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
from std_msgs.msg import String


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
        assert isinstance(node.pub_lifecycle_status, LifecyclePublisher)
        assert _spin_until(executor, lambda: node.pub_lifecycle_status.get_subscription_count() > 0)

        node.pub_lifecycle_status.publish(String(data='inactive'))
        assert not _spin_until(executor, lambda: bool(received), timeout=0.2)

        assert node.trigger_configure() == TransitionCallbackReturn.SUCCESS
        assert node.trigger_activate() == TransitionCallbackReturn.SUCCESS
        node.pub_lifecycle_status.publish(String(data='active'))
        assert _spin_until(executor, lambda: received == ['active'])

        assert node.trigger_deactivate() == TransitionCallbackReturn.SUCCESS
        node.pub_lifecycle_status.publish(String(data='inactive-again'))
        assert not _spin_until(executor, lambda: len(received) > 1, timeout=0.2)
    finally:
        executor.shutdown()
        node.destroy_node()
        harness.destroy_node()
