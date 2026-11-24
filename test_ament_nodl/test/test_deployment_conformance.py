# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Runnable CLI parameter checks against a running node."""

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


def generate_test_description():
    node = Node(
        package='test_ament_nodl',
        executable='conformance_fixture_node',
        name='fixture',
        namespace='/deployment',
        output='screen',
        ros_arguments=['--params-file', _PARAMETERS],
    )
    return LaunchDescription([node, ReadyToTest()])


def _conform(*extra):
    return subprocess.run(
        ['ros2', 'nodl', 'conform', _NODE, '--file', _CONTRACT, '--params-file', _PARAMETERS, *extra],
        capture_output=True,
        text=True,
        check=False,
    )


class TestDeploymentConformance(unittest.TestCase):
    def test_explicit_parameters_conform(self):
        result = _conform()
        assert result.returncode == 0, result.stderr

    def test_unapplied_value_fails(self):
        result = _conform('-p', 'limit:=6')
        assert result.returncode == 1
        assert '[value_mismatch]' in result.stderr, result.stderr
