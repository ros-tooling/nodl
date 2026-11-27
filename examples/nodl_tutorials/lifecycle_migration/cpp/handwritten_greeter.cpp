// SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
// SPDX-License-Identifier: Apache-2.0

#include <chrono>
#include <memory>
#include <string>

#include "rclcpp/rclcpp.hpp"
#include "rclcpp_lifecycle/lifecycle_node.hpp"
#include "std_msgs/msg/string.hpp"
#include "std_srvs/srv/trigger.hpp"

using std::chrono_literals::operator""ms;
using CallbackReturn = rclcpp_lifecycle::node_interfaces::LifecycleNodeInterface::CallbackReturn;

class Greeter : public rclcpp_lifecycle::LifecycleNode
{
public:
  Greeter()
  : rclcpp_lifecycle::LifecycleNode("greeter")
  {
    pub_greeting_ = create_publisher<std_msgs::msg::String>("greeting", 10);
    cli_notify_ = create_client<std_srvs::srv::Trigger>("notify");
  }

  CallbackReturn on_configure(const rclcpp_lifecycle::State & /*previous_state*/) override
  {
    sub_name_ = create_subscription<std_msgs::msg::String>(
      "name", 10, [this](std_msgs::msg::String::ConstSharedPtr msg) { greet(msg->data); });
    return CallbackReturn::SUCCESS;
  }

  CallbackReturn on_activate(const rclcpp_lifecycle::State & previous_state) override
  {
    rclcpp_lifecycle::LifecycleNode::on_activate(previous_state);
    greet("everyone");
    timer_ = create_wall_timer(500ms, [this] {
      greet("again");
      cli_notify_->async_send_request(std::make_shared<std_srvs::srv::Trigger::Request>());
    });
    return CallbackReturn::SUCCESS;
  }

  CallbackReturn on_deactivate(const rclcpp_lifecycle::State & previous_state) override
  {
    timer_.reset();
    std_msgs::msg::String goodbye;
    goodbye.data = "goodbye";
    pub_greeting_->publish(goodbye);
    return rclcpp_lifecycle::LifecycleNode::on_deactivate(previous_state);
  }

  CallbackReturn on_cleanup(const rclcpp_lifecycle::State & /*previous_state*/) override
  {
    sub_name_.reset();
    return CallbackReturn::SUCCESS;
  }

private:
  void greet(const std::string & name)
  {
    std_msgs::msg::String greeting;
    greeting.data = "hello " + name;
    pub_greeting_->publish(greeting);
  }

  rclcpp_lifecycle::LifecyclePublisher<std_msgs::msg::String>::SharedPtr pub_greeting_;
  rclcpp::Subscription<std_msgs::msg::String>::SharedPtr sub_name_;
  rclcpp::Client<std_srvs::srv::Trigger>::SharedPtr cli_notify_;
  rclcpp::TimerBase::SharedPtr timer_;
};

int main(int argc, char * argv[])
{
  rclcpp::init(argc, argv);
  auto node = std::make_shared<Greeter>();
  rclcpp::spin(node->get_node_base_interface());
  rclcpp::shutdown();
  return 0;
}
