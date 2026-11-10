# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""End-to-end test for generated rclpy parameters."""

import math

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


def test_nested_parameter_change_calls_hook_and_keeps_earlier_snapshot(ros_context):
    node = RecordingParametersNode()
    try:
        snapshot = node.params_

        result = node.set_parameters([Parameter('colour.r', value=0.5)])[0]

        assert result.successful
        assert [change.colour.r for change in node.changes] == [0.5]
        assert node.params_.colour.r == 0.5
        assert snapshot.colour.r == 0.8
        assert snapshot.colour is not node.params_.colour
    finally:
        # generate_parameter_library_py keeps nested defaults in a class attribute shared by every node, so restore the default for later nodes.
        node.set_parameters([Parameter('colour.r', value=0.8)])
        node.destroy_node()


def test_same_value_does_not_call_hook(ros_context):
    node = RecordingParametersNode()
    try:
        node.set_parameters([Parameter('colour.r', value=0.8), Parameter('max_speed', value=1.5)])
        node.set_parameters([Parameter('waypoints', value=[1.0, 2.0])])

        assert node.changes == []
    finally:
        node.destroy_node()


def test_array_change_calls_hook_and_repeated_nan_does_not(ros_context):
    node = RecordingParametersNode()
    try:
        node.set_parameters([Parameter('waypoints', value=[1.0, 3.0])])
        node.set_parameters([Parameter('waypoints', value=[float('nan')])])
        node.set_parameters([Parameter('waypoints', value=[float('nan')])])

        assert len(node.changes) == 2
        assert list(node.changes[0].waypoints) == [1.0, 3.0]
        assert math.isnan(node.changes[1].waypoints[0])
    finally:
        node.destroy_node()
