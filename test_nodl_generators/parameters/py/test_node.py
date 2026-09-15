# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""End-to-end test for generated rclpy parameters."""

import pytest
import rclpy

from test_nodl_generators.generated.parameters_node_base import ParametersNodeBase


@pytest.fixture
def ros_context():
    rclpy.init()
    try:
        yield
    finally:
        rclpy.shutdown()


def test_generated_parameters(ros_context):
    node = ParametersNodeBase()
    try:
        assert node.params_.max_speed == 1.5
        assert node.params_.robot_name == 'bot'
        assert node.params_.enabled is True
    finally:
        node.destroy_node()
