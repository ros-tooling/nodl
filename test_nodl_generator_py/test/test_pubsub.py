# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""End-to-end pub/sub test for the exported generator macro."""

import time

import pytest
import rclpy
from rclpy.executors import SingleThreadedExecutor
from rclpy.node import Node
from std_msgs.msg import String

from test_nodl_generator_py.pubsub_node_impl import PubsubNode


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


def test_echoes_through_generated_handles(ros_context):
    node = PubsubNode()
    harness = Node('test_harness')

    received = []
    harness.create_subscription(String, '/echo_out', lambda m: received.append(m.data), 10)
    pub = harness.create_publisher(String, '/echo_in', 10)

    executor = SingleThreadedExecutor()
    executor.add_node(node)
    executor.add_node(harness)
    try:
        assert node.get_name() == 'pubsub_node'
        assert hasattr(node, 'pub_echo_out')
        assert hasattr(node, 'sub_echo_in')
        assert _spin_until(executor, lambda: pub.get_subscription_count() > 0)

        pub.publish(String(data='hello'))
        assert _spin_until(executor, lambda: bool(received))
        assert received == ['echo: hello']
    finally:
        executor.shutdown()
        node.destroy_node()
        harness.destroy_node()
