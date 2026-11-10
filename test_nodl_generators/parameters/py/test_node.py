# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""End-to-end test for generated rclpy parameters."""

import pytest
import rclpy
from node_impl import RecordingParametersNode
from nodl_generated.test_nodl_generators.parameters_node_base import ParametersNodeBase
from rclpy.parameter import Parameter


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


def test_dynamic_parameter_updates_params_and_calls_hook_once(ros_context):
    node = RecordingParametersNode()
    try:
        result = node.set_parameters([Parameter('max_speed', value=2.5)])[0]

        assert result.successful
        assert node.params_.max_speed == 2.5
        assert [change.max_speed for change in node.changes] == [2.5]
        assert node.get_parameter('max_speed').value == 2.5
    finally:
        node.destroy_node()


def test_rejected_value_changes_neither_params_nor_hook(ros_context):
    node = RecordingParametersNode()
    try:
        result = node.set_parameters([Parameter('max_speed', value=-1.0)])[0]

        assert not result.successful
        assert node.params_.max_speed == 1.5
        assert node.changes == []
    finally:
        node.destroy_node()


def test_unrelated_parameter_does_not_call_hook(ros_context):
    node = RecordingParametersNode()
    try:
        result = node.set_parameters([Parameter('unrelated', value=5)])[0]

        assert result.successful
        assert node.get_parameter('unrelated').value == 5
        assert node.changes == []
        assert node.params_.max_speed == 1.5
    finally:
        node.destroy_node()


def test_hook_runs_before_the_change_is_committed(ros_context):
    node = RecordingParametersNode()
    try:
        node.set_parameters([Parameter('max_speed', value=2.5)])

        assert node.changes[0].max_speed == 2.5
        assert node.committed_during_hook == [1.5]
        assert node.get_parameter('max_speed').value == 2.5
    finally:
        node.destroy_node()


def test_snapshot_is_unaffected_by_later_updates(ros_context):
    node = RecordingParametersNode()
    try:
        snapshot = node.params_
        node.set_parameters([Parameter('max_speed', value=3.0)])

        assert snapshot.max_speed == 1.5
        assert node.params_.max_speed == 3.0
    finally:
        node.destroy_node()
