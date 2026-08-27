// SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
// SPDX-License-Identifier: Apache-2.0
#include <memory>

#include "services_node.hpp"  // NOLINT(build/include_subdir)

class TestNode : public ServicesNodeBase
{
  void on_trigger(
    std_srvs::srv::Trigger::Request::SharedPtr /*request*/,
    std_srvs::srv::Trigger::Response::SharedPtr /*response*/) override
  {}
};

int main(int argc, char ** argv)
{
  rclcpp::init(argc, argv);
  auto node = std::make_shared<TestNode>();
  rclcpp::shutdown();
  return 0;
}
