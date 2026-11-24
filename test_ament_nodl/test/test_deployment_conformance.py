# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Runnable deployment example, including unapplied values and forbidden QoS overrides."""

import subprocess
import unittest
from pathlib import Path

from launch import LaunchDescription
from launch_ros.actions import Node
from launch_testing.actions import ReadyToTest

_FIXTURES = Path(__file__).parent / 'fixtures'
_CONTRACT = str(_FIXTURES / 'conformance_fixture.nodl.yaml')
_PARAMETERS = str(_FIXTURES / 'conformance_fixture_parameters.yaml')
_NODE = '/deployment/fixture'
_QOS = 'qos_overrides./deployment/state.publisher.reliability:=best_effort'


def generate_test_description():
    node = Node(
        package='test_ament_nodl',
        executable='conformance_fixture_node',
        name='fixture',
        namespace='/deployment',
        output='screen',
        ros_arguments=['--params-file', _PARAMETERS, '-p', _QOS],
    )
    return LaunchDescription([node, ReadyToTest()])


def _conform(*extra):
    return subprocess.run(
        ['ros2', 'nodl', 'conform', _NODE, '--file', _CONTRACT, '--params-file', _PARAMETERS, '-p', _QOS, *extra],
        capture_output=True,
        text=True,
        check=False,
    )


class TestDeploymentConformance(unittest.TestCase):
    def test_deployment_and_permitted_qos_conform(self):
        result = _conform()
        assert result.returncode == 0, result.stderr

    def test_unapplied_value_fails(self):
        result = _conform('-p', 'limit:=6')
        assert result.returncode == 1
        assert '[value_mismatch]' in result.stderr, result.stderr

    def test_constraint_violation_fails(self):
        result = _conform('-p', 'limit:=20')
        assert result.returncode == 1
        assert '[constraint_mismatch]' in result.stderr, result.stderr

    def test_unapplied_qos_fails(self):
        result = _conform('-p', 'qos_overrides./deployment/state.publisher.reliability:=reliable')
        assert result.returncode == 1
        assert '[qos_mismatch]' in result.stderr, result.stderr

    def test_unpermitted_qos_fails(self):
        result = _conform('-p', 'qos_overrides./deployment/state.publisher.durability:=transient_local')
        assert result.returncode == 1
        assert '[configuration_error]' in result.stderr, result.stderr
