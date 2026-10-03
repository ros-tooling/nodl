// SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
// SPDX-License-Identifier: Apache-2.0
#include <memory>

#include "test_nodl_generators/cpp_services_node_base.hpp"

class TestNode : public CppServicesNodeBase
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
