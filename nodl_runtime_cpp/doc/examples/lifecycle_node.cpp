// SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
// SPDX-License-Identifier: Apache-2.0
#include "nodl_runtime_cpp/lifecycle_node.hpp"

#include <chrono>
#include <memory>
#include <string>

#include "rclcpp/create_publisher.hpp"
#include "rclcpp/rclcpp.hpp"
#include "std_msgs/msg/string.hpp"

/// Example of a non-generated node that uses `nodl_runtime_cpp::LifecycleNode`.
/**
 * It registers a latched publisher and a subscription, which exist only while the node is active,
 * and greets on a timer that runs between `handle_activate` and `handle_deactivate`.
 * The endpoints are registered by hand to keep the example self-contained, where a generated node registers its own.
 */
class Greeter : public nodl_runtime_cpp::LifecycleNode
{
public:
  Greeter()
  : nodl_runtime_cpp::LifecycleNode("greeter")
  {
    manage(greeting_, [this] {
      return rclcpp::create_publisher<std_msgs::msg::String>(*this, "greeting", rclcpp::QoS(1).transient_local());
    });
    manage(name_, [this] {
      return create_subscription<std_msgs::msg::String>(
        "name", 10, [this](std_msgs::msg::String::ConstSharedPtr msg) { greet(msg->data); });
    });
  }

protected:
  // The publisher and the subscription exist here.
  CallbackReturn handle_activate(const rclcpp_lifecycle::State & /*previous_state*/) override
  {
    greet("everyone");
    timer_ = create_wall_timer(std::chrono::seconds(1), [this] { greet("again"); });
    return CallbackReturn::SUCCESS;
  }

  // The timer stops here, before the publisher it uses is destroyed.
  CallbackReturn handle_deactivate(const rclcpp_lifecycle::State & /*previous_state*/) override
  {
    timer_.reset();
    RCLCPP_INFO(get_logger(), "goodbye");
    return CallbackReturn::SUCCESS;
  }

private:
  void greet(const std::string & name)
  {
    std_msgs::msg::String greeting;
    greeting.data = "hello " + name;
    greeting_->publish(greeting);
  }

  rclcpp::Publisher<std_msgs::msg::String>::SharedPtr greeting_;
  rclcpp::Subscription<std_msgs::msg::String>::SharedPtr name_;
  rclcpp::TimerBase::SharedPtr timer_;
};

int main(int argc, char ** argv)
{
  rclcpp::init(argc, argv);
  auto node = std::make_shared<Greeter>();
  rclcpp::spin(node->get_node_base_interface());
  rclcpp::shutdown();
  return 0;
}
