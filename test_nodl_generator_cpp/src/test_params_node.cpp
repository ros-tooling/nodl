// SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
// SPDX-License-Identifier: Apache-2.0
#include <memory>

#include "params_node.hpp"  // NOLINT(build/include_subdir)

class TestNode : public ParamsNodeBase
{
public:
  TestNode()
  {
    // Verify parameter access compiles (param_listener_ and params_ are protected).
    auto params = param_listener_.get_params();
    (void)params.max_speed;
    (void)params.robot_name;
    (void)params.enabled;
  }
};

int main(int argc, char ** argv)
{
  rclcpp::init(argc, argv);
  auto node = std::make_shared<TestNode>();
  rclcpp::shutdown();
  return 0;
}
