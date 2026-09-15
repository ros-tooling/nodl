// SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
// SPDX-License-Identifier: Apache-2.0

#include <memory>

#include "navigate_to_pose_client_base.hpp"  // NOLINT(build/include_subdir)
#include "navigation.hpp"  // NOLINT(build/include_subdir)
#include "rclcpp/rclcpp.hpp"

class NavigateToPoseClientNodl : public NavigateToPoseClientBase
{
public:
  NavigateToPoseActionClient::SharedPtr client() const
  {
    return action_cli_navigate_to_pose_;
  }
};

int main(int argc, char * argv[])
{
  rclcpp::init(argc, argv);
  auto node = std::make_shared<NavigateToPoseClientNodl>();
  const int result = run_navigation(argc, argv, node, node->client());
  node.reset();
  if (rclcpp::ok()) {
    rclcpp::shutdown();
  }
  return result;
}
