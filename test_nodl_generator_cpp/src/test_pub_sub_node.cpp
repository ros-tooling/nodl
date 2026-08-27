// SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
// SPDX-License-Identifier: Apache-2.0
#include <memory>

#include "pub_sub_node.hpp"  // NOLINT(build/include_subdir)

class TestNode : public PubSubNodeBase
{
  void on_cmd_vel(geometry_msgs::msg::Twist::ConstSharedPtr /*msg*/) override
  {}
};

int main(int argc, char ** argv)
{
  rclcpp::init(argc, argv);
  auto node = std::make_shared<TestNode>();
  rclcpp::shutdown();
  return 0;
}
