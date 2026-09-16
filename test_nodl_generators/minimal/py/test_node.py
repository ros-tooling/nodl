# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Runtime test for the implicit rclpy Node base."""

import pytest
import rclpy
from node_impl import MinimalNode
from rclpy.node import Node


@pytest.fixture
def ros_context():
    rclpy.init()
    try:
        yield
    finally:
        rclpy.shutdown()


def test_implicit_node_base(ros_context):
    node = MinimalNode()
    try:
        assert isinstance(node, Node)
        assert node.get_name() == 'minimal_node'
    finally:
        node.destroy_node()
