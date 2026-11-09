// SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
// SPDX-License-Identifier: Apache-2.0
#include "nodl_runtime_cpp/lifecycle_node.hpp"

#include <memory>

#include "rclcpp/rclcpp.hpp"
#include "std_msgs/msg/string.hpp"

/// Example of a non-generated node that uses `nodl_runtime_cpp::LifecycleNode`, and publishes a greeting when it activates.
/**
 * The endpoint is created by hand to keep the example self-contained, where a generated node creates its own.
 */
class Greeter : public nodl_runtime_cpp::LifecycleNode
{
public:
  Greeter()
  : nodl_runtime_cpp::LifecycleNode("greeter")
  , publisher_(create_publisher<std_msgs::msg::String>("greeting", 10))
  {}

protected:
  // Lifecycle publishers are already active here, so the hook never activates them.
  CallbackReturn handle_activate(const rclcpp_lifecycle::State & /*previous_state*/) override
  {
    std_msgs::msg::String greeting;
    greeting.data = "hello";
    publisher_->publish(greeting);
    return CallbackReturn::SUCCESS;
  }

  // Lifecycle publishers are deactivated after this hook returns SUCCESS.
  CallbackReturn handle_deactivate(const rclcpp_lifecycle::State & /*previous_state*/) override
  {
    RCLCPP_INFO(get_logger(), "goodbye");
    return CallbackReturn::SUCCESS;
  }

private:
  rclcpp_lifecycle::LifecyclePublisher<std_msgs::msg::String>::SharedPtr publisher_;
};

int main(int argc, char ** argv)
{
  rclcpp::init(argc, argv);
  auto node = std::make_shared<Greeter>();
  rclcpp::spin(node->get_node_base_interface());
  rclcpp::shutdown();
  return 0;
}
