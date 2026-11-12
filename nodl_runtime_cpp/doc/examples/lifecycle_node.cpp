// SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
// SPDX-License-Identifier: Apache-2.0
#include "nodl_runtime_cpp/lifecycle_node.hpp"

#include <chrono>
#include <string>

#include "rclcpp/create_publisher.hpp"
#include "rclcpp/rclcpp.hpp"
#include "std_msgs/msg/string.hpp"

/// Example of a non-generated node that uses `nodl_runtime_cpp::LifecycleNode`.
/**
 * It holds a latched publisher, registers a subscription that exists only while the node is active,
 * and greets on a timer that runs between `handle_activate` and `handle_deactivate`.
 * The subscription is registered by hand to keep the example self-contained, where a generated node registers its own.
 */
class Greeter : public nodl_runtime_cpp::LifecycleNode
{
public:
  Greeter()
  : nodl_runtime_cpp::LifecycleNode("greeter")
  , pub_greeting_(create_publisher<std_msgs::msg::String>("greeting", rclcpp::QoS(1).transient_local()))
  {
    manage(sub_name_, [this] {
      return create_subscription<std_msgs::msg::String>(
        "name", rclcpp::QoS(10), std::bind(&Greeter::on_name, this, std::placeholders::_1));
    });
  }

protected:
  // The subscription exists here, and is null in every other state.
  CallbackReturn handle_activate(const rclcpp_lifecycle::State & /*previous_state*/) override
  {
    greet("everyone");
    timer_ = create_wall_timer(std::chrono::seconds(1), [this] { greet("again"); });
    return CallbackReturn::SUCCESS;
  }

  // The timer stops here, before the publisher it uses is destroyed.
  // This hook also runs first on shutdown and error from the active state.
  CallbackReturn handle_deactivate(const rclcpp_lifecycle::State & /*previous_state*/) override
  {
    timer_.reset();
    RCLCPP_INFO(get_logger(), "goodbye");
    return CallbackReturn::SUCCESS;
  }

private:
  void on_name(std_msgs::msg::String::ConstSharedPtr msg)
  {
    greet(msg->data);
  }

  void greet(const std::string & name)
  {
    std_msgs::msg::String greeting;
    greeting.data = "hello " + name;
    pub_greeting_->publish(greeting);
  }

  rclcpp::Publisher<std_msgs::msg::String>::SharedPtr pub_greeting_;
  rclcpp::Subscription<std_msgs::msg::String>::SharedPtr sub_name_;
  rclcpp::TimerBase::SharedPtr timer_;
};

int main(int argc, char ** argv)
{
  rclcpp::init(argc, argv);
  Greeter node;
  rclcpp::spin(node.get_node_base_interface());
  rclcpp::shutdown();
  return 0;
}
