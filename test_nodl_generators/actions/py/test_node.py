# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""End-to-end test for generated rclpy actions."""

import time

import pytest
import rclpy
from example_interfaces.action import Fibonacci
from node_impl import ActionsNode
from rclpy.action import ActionClient
from rclpy.executors import SingleThreadedExecutor
from rclpy.node import Node


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


def test_generated_actions(ros_context):
    node = ActionsNode()
    harness = Node('test_harness')
    client = ActionClient(harness, Fibonacci, '/fibonacci')
    executor = SingleThreadedExecutor()
    executor.add_node(node)
    executor.add_node(harness)
    try:
        assert hasattr(node, 'action_srv_fibonacci')
        assert hasattr(node, 'action_cli_delegate_fibonacci')
        assert client.wait_for_server(timeout_sec=5.0)
        rejected_future = client.send_goal_async(Fibonacci.Goal(order=-1))
        _spin_until(executor, rejected_future.done)
        assert not rejected_future.result().accepted

        goal_future = client.send_goal_async(Fibonacci.Goal(order=5))
        _spin_until(executor, goal_future.done)
        assert goal_future.result().accepted
        result_future = goal_future.result().get_result_async()
        _spin_until(executor, result_future.done)
        assert list(result_future.result().result.sequence) == [0, 1, 1, 2, 3]
    finally:
        executor.shutdown()
        node.destroy_node()
        harness.destroy_node()
