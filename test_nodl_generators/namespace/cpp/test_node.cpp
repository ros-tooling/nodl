// SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
// SPDX-License-Identifier: Apache-2.0
#include <memory>

#include "test_nodl_generators/cpp_namespace_node_base.hpp"

class TestNode : public nodl_test::nodl_test::CppNamespaceNodeBase
{
public:
  TestNode()
  {
    // Verify the class and the parameter structs both live in nodl_test::nodl_test.
    nodl_test::nodl_test::cpp_namespace_node_base::Params params = param_listener_.get_params();
    (void)params.max_speed;
    (void)params_.robot_name;
    (void)pub_status_;
  }
};

int main(int argc, char ** argv)
{
  rclcpp::init(argc, argv);
  auto node = std::make_shared<TestNode>();
  rclcpp::shutdown();
  return 0;
}
