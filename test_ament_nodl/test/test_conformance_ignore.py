# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""A node with an endpoint its document does not declare, checked with and without ignore rules."""

import subprocess
import unittest
from pathlib import Path

import pytest
from launch import LaunchDescription
from launch_ros.actions import Node
from launch_testing.actions import ReadyToTest

from ros2nodl.conformance import assert_conforms

_NODL_FILE = str(Path(__file__).parent / 'fixtures' / 'conformance_fixture.nodl.yaml')
_NODE_FQN = '/conformance_injected/fixture'
_IGNORE = 'publisher:/topic_statistics'


def generate_test_description():
    node = Node(
        package='test_ament_nodl',
        executable='conformance_injected_node',
        name='fixture',
        namespace='/conformance_injected',
        output='screen',
        ros_arguments=['-p', 'limit:=5', '-p', 'mode:=1_000'],
    )
    return LaunchDescription([node, ReadyToTest()])


def _conform_cli(*extra):
    return subprocess.run(
        ['ros2', 'nodl', 'conform', _NODE_FQN, '--file', _NODL_FILE, *extra],
        capture_output=True,
        text=True,
        check=False,
    )


class TestConformanceIgnore(unittest.TestCase):
    def test_undeclared_endpoint_fails_without_ignore(self):
        with pytest.raises(AssertionError, match=r"\[extra\] publishers '/topic_statistics'"):
            assert_conforms(nodl_file=_NODL_FILE, node_fqn=_NODE_FQN)

    def test_undeclared_endpoint_passes_with_ignore(self):
        report = assert_conforms(nodl_file=_NODL_FILE, node_fqn=_NODE_FQN, ignore=[_IGNORE])

        assert [difference.name for difference in report.ignored] == ['/topic_statistics']

    def test_ignore_of_another_endpoint_still_fails(self):
        with pytest.raises(AssertionError, match=r"\[extra\] publishers '/topic_statistics'"):
            assert_conforms(nodl_file=_NODL_FILE, node_fqn=_NODE_FQN, ignore=['publisher:/other'])

    def test_cli_fails_without_ignore(self):
        result = _conform_cli()

        assert result.returncode == 1
        assert "[extra] publishers '/topic_statistics'" in result.stderr

    def test_cli_passes_with_ignore_and_names_the_ignored_endpoint(self):
        result = _conform_cli('--ignore', _IGNORE)

        assert result.returncode == 0, result.stderr
        assert f'{_NODE_FQN}: conforms' in result.stdout
        assert "ignored [extra] publishers '/topic_statistics'" in result.stdout
