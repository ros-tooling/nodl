// SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
// SPDX-License-Identifier: Apache-2.0

#include <memory>

#include "nav2_msgs/action/navigate_to_pose.hpp"
#include "navigation.hpp"  // NOLINT(build/include_subdir)
#include "rclcpp/rclcpp.hpp"
#include "rclcpp_action/rclcpp_action.hpp"

class NavigateToPoseClient : public rclcpp::Node
{
public:
  NavigateToPoseClient()
  : Node("navigate_to_pose_client")
  , client_(rclcpp_action::create_client<nav2_msgs::action::NavigateToPose>(this, "navigate_to_pose"))
  {}

  NavigateToPoseActionClient::SharedPtr client() const
  {
    return client_;
  }

private:
  NavigateToPoseActionClient::SharedPtr client_;
};

int main(int argc, char * argv[])
{
  rclcpp::init(argc, argv);
  auto node = std::make_shared<NavigateToPoseClient>();
  const int result = run_navigation(argc, argv, node, node->client());
  node.reset();
  if (rclcpp::ok()) {
    rclcpp::shutdown();
  }
  return result;
}
