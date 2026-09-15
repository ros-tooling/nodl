// SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
// SPDX-License-Identifier: Apache-2.0

#pragma once

#include <memory>

#include "nav2_msgs/action/navigate_to_pose.hpp"
#include "rclcpp/node.hpp"
#include "rclcpp_action/client.hpp"

using NavigateToPoseActionClient = rclcpp_action::Client<nav2_msgs::action::NavigateToPose>;

int run_navigation(
  int argc, char * argv[], const rclcpp::Node::SharedPtr & node, const NavigateToPoseActionClient::SharedPtr & client);
