// SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
// SPDX-License-Identifier: Apache-2.0
#include <memory>

#include "kitchen_sink_node.hpp"  // NOLINT(build/include_subdir)

class TestNode : public KitchenSinkNodeBase
{
  void on_cmd_vel(geometry_msgs::msg::Twist::ConstSharedPtr /*msg*/) override
  {}

  void on_trigger(
    std_srvs::srv::Trigger::Request::SharedPtr /*request*/,
    std_srvs::srv::Trigger::Response::SharedPtr /*response*/) override
  {}

  rclcpp_action::GoalResponse on_fibonacci_goal(
    const rclcpp_action::GoalUUID & /*uuid*/,
    std::shared_ptr<const example_interfaces::action::Fibonacci::Goal> /*goal*/) override
  {
    return rclcpp_action::GoalResponse::ACCEPT_AND_EXECUTE;
  }

  rclcpp_action::CancelResponse on_fibonacci_cancel(
    std::shared_ptr<rclcpp_action::ServerGoalHandle<example_interfaces::action::Fibonacci>>
    /*goal_handle*/) override
  {
    return rclcpp_action::CancelResponse::ACCEPT;
  }

  void on_fibonacci_accepted(std::shared_ptr<rclcpp_action::ServerGoalHandle<example_interfaces::action::Fibonacci>>
                             /*goal_handle*/) override
  {}
};

int main(int argc, char ** argv)
{
  rclcpp::init(argc, argv);
  auto node = std::make_shared<TestNode>();
  rclcpp::shutdown();
  return 0;
}
