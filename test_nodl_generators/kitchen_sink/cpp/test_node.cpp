// SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
// SPDX-License-Identifier: Apache-2.0
#include <memory>
#include <string>

#include "test_nodl_generators/cpp_kitchen_sink_node_base.hpp"

class TestNode : public CppKitchenSinkNodeBase
{
public:
  bool clients_keep_ros_names() const
  {
    return std::string(cli_toggle_->get_service_name()) == "/set_bool" && action_cli_counter_ &&
           pub_state_->get_topic_name() == std::string("/status");
  }

private:
  void on_velocity(geometry_msgs::msg::Twist::ConstSharedPtr /*msg*/) override
  {}

  void on_velocity(
    std_srvs::srv::Trigger::Request::SharedPtr /*request*/,
    std_srvs::srv::Trigger::Response::SharedPtr /*response*/) override
  {}

  rclcpp_action::GoalResponse on_sequence_goal(
    const rclcpp_action::GoalUUID & /*uuid*/,
    std::shared_ptr<const example_interfaces::action::Fibonacci::Goal> /*goal*/) override
  {
    return rclcpp_action::GoalResponse::ACCEPT_AND_EXECUTE;
  }

  rclcpp_action::CancelResponse on_sequence_cancel(
    std::shared_ptr<rclcpp_action::ServerGoalHandle<example_interfaces::action::Fibonacci>>
    /*goal_handle*/) override
  {
    return rclcpp_action::CancelResponse::ACCEPT;
  }

  void on_sequence_accepted(std::shared_ptr<rclcpp_action::ServerGoalHandle<example_interfaces::action::Fibonacci>>
                            /*goal_handle*/) override
  {}
};

int main(int argc, char ** argv)
{
  rclcpp::init(argc, argv);
  auto node = std::make_shared<TestNode>();
  const bool valid = node->clients_keep_ros_names();
  rclcpp::shutdown();
  return valid ? 0 : 1;
}
