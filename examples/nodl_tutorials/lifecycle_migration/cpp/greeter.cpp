// SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
// SPDX-License-Identifier: Apache-2.0

#include <chrono>
#include <memory>
#include <string>

#include "nodl_runtime_cpp/managed.hpp"
#include "nodl_tutorial_lifecycle_migration/greeter_base.hpp"
#include "rclcpp/rclcpp.hpp"
#include "std_msgs/msg/string.hpp"
#include "std_srvs/srv/trigger.hpp"

using std::chrono_literals::operator""ms;

class Greeter : public GreeterBase
{
protected:
  void on_name(std_msgs::msg::String::ConstSharedPtr msg) override
  {
    greet(msg->data);
  }

  // The client is not handed out while the node is inactive, so this sends nothing.
  CallbackReturn handle_configure(const rclcpp_lifecycle::State & /*previous_state*/) override
  {
    notify();
    return CallbackReturn::SUCCESS;
  }

  CallbackReturn handle_activate(const rclcpp_lifecycle::State & /*previous_state*/) override
  {
    greet("everyone");
    return CallbackReturn::SUCCESS;
  }

  CallbackReturn handle_deactivate(const rclcpp_lifecycle::State & /*previous_state*/) override
  {
    std_msgs::msg::String goodbye;
    goodbye.data = "goodbye";
    pub_greeting_->publish(goodbye);
    return CallbackReturn::SUCCESS;
  }

private:
  void greet(const std::string & name)
  {
    std_msgs::msg::String greeting;
    greeting.data = "hello " + name;
    pub_greeting_->publish(greeting);
  }

  void on_timer()
  {
    greet("again");
    notify();
  }

  void notify()
  {
    if (auto client = cli_notify_.get()) {
      client->async_send_request(std::make_shared<std_srvs::srv::Trigger::Request>());
    }
  }

  nodl_runtime_cpp::Managed<rclcpp::TimerBase> timer_{
    *this, [this] { return create_wall_timer(500ms, [this] { on_timer(); }); }};
};

int main(int argc, char * argv[])
{
  rclcpp::init(argc, argv);
  auto node = std::make_shared<Greeter>();
  rclcpp::spin(node->get_node_base_interface());
  rclcpp::shutdown();
  return 0;
}
