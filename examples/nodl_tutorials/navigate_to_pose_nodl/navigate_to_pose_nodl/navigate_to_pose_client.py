#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Original action-client implementation used as the migration baseline."""

from nav2_msgs.action import NavigateToPose
from rclpy.action import ActionClient
from rclpy.node import Node

from navigate_to_pose_nodl.navigation import run


class NavigateToPoseClient(Node):
    """Create the ROS action client directly in application code."""

    def __init__(self):
        super().__init__('navigate_to_pose_client_py')
        self.action_cli_navigate_to_pose = ActionClient(self, NavigateToPose, 'navigate_to_pose')


def main(args=None):
    """Send one navigation goal with the original client."""
    return run(NavigateToPoseClient, args)


if __name__ == '__main__':
    raise SystemExit(main())
