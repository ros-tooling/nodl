# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Behavior shared by the conventional and NoDL-backed navigation clients."""

import argparse
import sys

import rclpy
from action_msgs.msg import GoalStatus
from nav2_msgs.action import NavigateToPose
from rclpy.utilities import remove_ros_args


def goal_coordinates(args=None):
    """Read a map-frame target while leaving ROS arguments for rclpy."""
    command = sys.argv if args is None else [sys.argv[0], *args]
    parser = argparse.ArgumentParser(description='Send one Nav2 NavigateToPose goal.')
    parser.add_argument('x', type=float, nargs='?', help='Goal x coordinate in the map frame.')
    parser.add_argument('y', type=float, nargs='?', help='Goal y coordinate in the map frame.')
    coordinates = parser.parse_args(remove_ros_args(args=command)[1:])
    if (coordinates.x is None) != (coordinates.y is None):
        parser.error('provide both x and y, or neither')
    return coordinates


def navigate(node, x, y):
    """Send one goal through the action client supplied by the node."""
    client = node.action_cli_navigate_to_pose
    if not client.wait_for_server(timeout_sec=10.0):
        node.get_logger().error('NavigateToPose server was not available')
        return False

    goal = NavigateToPose.Goal()
    goal.pose.header.frame_id = 'map'
    goal.pose.header.stamp = node.get_clock().now().to_msg()
    goal.pose.pose.position.x = x
    goal.pose.pose.position.y = y
    goal.pose.pose.orientation.w = 1.0

    goal_future = client.send_goal_async(goal)
    rclpy.spin_until_future_complete(node, goal_future)
    goal_handle = goal_future.result()
    if goal_handle is None or not goal_handle.accepted:
        node.get_logger().error('Navigation goal was rejected')
        return False

    node.get_logger().info(f'Navigating to ({x:.2f}, {y:.2f})')
    result_future = goal_handle.get_result_async()
    rclpy.spin_until_future_complete(node, result_future)
    result = result_future.result()
    succeeded = result is not None and result.status == GoalStatus.STATUS_SUCCEEDED
    node.get_logger().info('Navigation succeeded' if succeeded else 'Navigation failed')
    return succeeded


def run(client_type, args=None):
    """Run either client implementation with the same navigation behavior."""
    coordinates = goal_coordinates(args)
    rclpy.init(args=args)
    node = client_type()
    try:
        # With no goal, keep the interface available for the headless conformance test.
        if coordinates.x is None:
            try:
                rclpy.spin(node)
            except KeyboardInterrupt:
                pass
            return 0
        return 0 if navigate(node, coordinates.x, coordinates.y) else 1
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
