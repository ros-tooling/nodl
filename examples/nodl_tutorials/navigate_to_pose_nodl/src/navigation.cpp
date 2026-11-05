// SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
// SPDX-License-Identifier: Apache-2.0

#include "navigation.hpp"  // NOLINT(build/include_subdir)

#include <chrono>
#include <string>
#include <vector>

#include "rclcpp/rclcpp.hpp"
#include "rclcpp_action/rclcpp_action.hpp"

using std::chrono_literals::operator""s;

int run_navigation(
  int argc, char * argv[], const rclcpp::Node::SharedPtr & node, const NavigateToPoseActionClient::SharedPtr & client)
{
  const std::vector<std::string> args = rclcpp::remove_ros_arguments(argc, argv);
  if (args.size() == 1) {
    // Keep the interface available for the headless conformance test.
    rclcpp::spin(node);
    return 0;
  }
  if (args.size() != 3) {
    RCLCPP_ERROR(node->get_logger(), "usage: %s [x y]", args.front().c_str());
    return 2;
  }

  double x;
  double y;
  try {
    x = std::stod(args[1]);
    y = std::stod(args[2]);
  } catch (const std::exception & error) {
    RCLCPP_ERROR(node->get_logger(), "invalid coordinates: %s", error.what());
    return 2;
  }

  if (!client->wait_for_action_server(10s)) {
    RCLCPP_ERROR(node->get_logger(), "NavigateToPose server was not available");
    return 1;
  }

  nav2_msgs::action::NavigateToPose::Goal goal;
  goal.pose.header.frame_id = "map";
  goal.pose.header.stamp = node->get_clock()->now();
  goal.pose.pose.position.x = x;
  goal.pose.pose.position.y = y;
  goal.pose.pose.orientation.w = 1.0;

  auto goal_future = client->async_send_goal(goal);
  if (rclcpp::spin_until_future_complete(node, goal_future) != rclcpp::FutureReturnCode::SUCCESS) {
    RCLCPP_ERROR(node->get_logger(), "Navigation goal could not be sent");
    return 1;
  }
  const auto goal_handle = goal_future.get();
  if (!goal_handle) {
    RCLCPP_ERROR(node->get_logger(), "Navigation goal was rejected");
    return 1;
  }

  RCLCPP_INFO(node->get_logger(), "Navigating to (%.2f, %.2f)", x, y);
  auto result_future = client->async_get_result(goal_handle);
  if (rclcpp::spin_until_future_complete(node, result_future) != rclcpp::FutureReturnCode::SUCCESS) {
    RCLCPP_ERROR(node->get_logger(), "Navigation result was not available");
    return 1;
  }

  const bool succeeded = result_future.get().code == rclcpp_action::ResultCode::SUCCEEDED;
  RCLCPP_INFO(node->get_logger(), "Navigation %s", succeeded ? "succeeded" : "failed");
  return succeeded ? 0 : 1;
}
