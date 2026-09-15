# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Verify the installed contract and both implementations' action-client boundary."""

from pathlib import Path

import pytest
import rclpy
from ament_index_python.packages import get_package_share_directory
from ament_index_python.resources import get_resource
from navigate_to_pose_nodl.navigate_to_pose_client import NavigateToPoseClient
from navigate_to_pose_nodl.navigate_to_pose_client_nodl import NavigateToPoseClientNodl
from rclpy.action import ActionClient

PACKAGE = 'navigate_to_pose_nodl'
DOCUMENT = 'navigate_to_pose_client'
EXPECTED = Path(__file__).parent / 'expected'


def test_registered_document_matches_installed_source():
    content, prefix = get_resource('nodl', f'{PACKAGE}__{DOCUMENT}')

    assert prefix
    installed = Path(get_package_share_directory(PACKAGE)) / 'nodl' / f'{DOCUMENT}.nodl.yaml'
    assert installed.read_text() == content


@pytest.mark.parametrize('client_type', [NavigateToPoseClient, NavigateToPoseClientNodl])
def test_client_exposes_navigate_to_pose_action(client_type):
    rclpy.init()
    node = client_type()
    try:
        assert isinstance(node.action_cli_navigate_to_pose, ActionClient)
    finally:
        node.destroy_node()
        rclpy.shutdown()


def test_documented_generated_wiring_matches_build():
    generated = Path.cwd() / 'nodl_generated'
    cpp = generated / 'navigate_to_pose_client_base'
    actual_cpp = (
        '// navigate_to_pose_client_base.hpp\n'
        + (cpp / 'navigate_to_pose_client_base.hpp').read_text()
        + '\n// navigate_to_pose_client_base.cpp\n'
        + (cpp / 'navigate_to_pose_client_base.cpp').read_text()
    )
    python = (
        generated / 'navigate_to_pose_client_py_base' / PACKAGE / 'generated' / 'navigate_to_pose_client_py_base.py'
    )

    assert actual_cpp.strip() == (EXPECTED / 'generated_cpp.txt').read_text().strip()
    assert python.read_text().strip() == (EXPECTED / 'generated_python.txt').read_text().strip()
