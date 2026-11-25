// SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
// SPDX-License-Identifier: Apache-2.0

// A lifecycle node that creates its subscription on activation, so no test sees it before the node is active.
// CONFIGURE_FAILS makes the configure transition fail.
// AUTOSTART activates the node itself, so a test can start from an active node.

#include <memory>

#include "rclcpp/rclcpp.hpp"
#include "rclcpp_lifecycle/lifecycle_node.hpp"
#include "std_msgs/msg/string.hpp"

using CallbackReturn = rclcpp_lifecycle::node_interfaces::LifecycleNodeInterface::CallbackReturn;

class LifecycleFixtureNode : public rclcpp_lifecycle::LifecycleNode
{
public:
  LifecycleFixtureNode()
  : LifecycleNode("lifecycle_fixture")
  {}

  CallbackReturn on_configure(const rclcpp_lifecycle::State &) override
  {
#ifdef CONFIGURE_FAILS
    return CallbackReturn::FAILURE;
#else
    return CallbackReturn::SUCCESS;
#endif
  }

  CallbackReturn on_activate(const rclcpp_lifecycle::State & state) override
  {
    LifecycleNode::on_activate(state);
    subscription_ = create_subscription<std_msgs::msg::String>(
      "command",
      rclcpp::QoS(rclcpp::KeepLast(10)).reliable().durability_volatile(),
      [](std_msgs::msg::String::ConstSharedPtr) {});
    return CallbackReturn::SUCCESS;
  }

  CallbackReturn on_deactivate(const rclcpp_lifecycle::State & state) override
  {
    subscription_.reset();
    return LifecycleNode::on_deactivate(state);
  }

private:
  rclcpp::Subscription<std_msgs::msg::String>::SharedPtr subscription_;
};

int main(int argc, char ** argv)
{
  rclcpp::init(argc, argv);
  auto node = std::make_shared<LifecycleFixtureNode>();
#ifdef AUTOSTART
  node->configure();
  node->activate();
#endif
  rclcpp::spin(node->get_node_base_interface());
  rclcpp::shutdown();
  return 0;
}
