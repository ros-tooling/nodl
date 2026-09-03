# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""End-to-end test for generated rclpy interfaces."""

import time

import pytest
import rclpy
from example_interfaces.action import Fibonacci
from example_interfaces.srv import AddTwoInts
from rclpy.action import ActionClient
from rclpy.executors import SingleThreadedExecutor
from rclpy.node import Node
from std_msgs.msg import String

from test_nodl_generator_py.interfaces_node_impl import InterfacesNode


@pytest.fixture
def ros_context():
    rclpy.init()
    try:
        yield
    finally:
        rclpy.shutdown()


def _spin_until(executor, predicate, timeout=5.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline and not predicate():
        executor.spin_once(timeout_sec=0.05)
    assert predicate()


def test_generated_interfaces(ros_context):
    node = InterfacesNode()
    harness = Node('test_harness')
    received = []
    harness.create_subscription(String, '/echo_out', lambda message: received.append(message.data), 10)
    publisher = harness.create_publisher(String, '/echo_in', 10)
    service_client = harness.create_client(AddTwoInts, '/add')
    action_client = ActionClient(harness, Fibonacci, '/fibonacci')

    executor = SingleThreadedExecutor()
    executor.add_node(node)
    executor.add_node(harness)
    try:
        assert node.get_parameter('greeting').value == 'hello'
        assert hasattr(node, 'cli_delegate_add')
        assert hasattr(node, 'action_client_delegate_fibonacci')

        _spin_until(executor, lambda: publisher.get_subscription_count() > 0)
        publisher.publish(String(data='world'))
        _spin_until(executor, lambda: received)
        assert received == ['hello: world']

        assert service_client.wait_for_service(timeout_sec=5.0)
        service_future = service_client.call_async(AddTwoInts.Request(a=2, b=3))
        _spin_until(executor, service_future.done)
        assert service_future.result().sum == 5

        assert action_client.wait_for_server(timeout_sec=5.0)
        goal_future = action_client.send_goal_async(Fibonacci.Goal(order=5))
        _spin_until(executor, goal_future.done)
        assert goal_future.result().accepted
        result_future = goal_future.result().get_result_async()
        _spin_until(executor, result_future.done)
        assert list(result_future.result().result.sequence) == [0, 1, 1, 2, 3]
    finally:
        executor.shutdown()
        node.destroy_node()
        harness.destroy_node()
