# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""End-to-end test for generated rclpy services."""

import time

import pytest
import rclpy
from example_interfaces.srv import AddTwoInts
from node_impl import ServicesNode
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


def test_generated_services(ros_context):
    node = ServicesNode()
    harness = Node('test_harness')
    client = harness.create_client(AddTwoInts, '/add')
    executor = SingleThreadedExecutor()
    executor.add_node(node)
    executor.add_node(harness)
    try:
        assert hasattr(node, 'srv_add')
        assert hasattr(node, 'cli_delegate_add')
        assert client.wait_for_service(timeout_sec=5.0)
        future = client.call_async(AddTwoInts.Request(a=2, b=3))
        _spin_until(executor, future.done)
        assert future.result().sum == 5
    finally:
        executor.shutdown()
        node.destroy_node()
        harness.destroy_node()
