// GENERATED FILE — do not edit. Regenerated from NoDL by nodl_generator_cpp.
#include "my_node.hpp"

MyNodeBase::MyNodeBase(const rclcpp::NodeOptions & options)
: rclcpp::Node("my_node", options)
{

  // Create action servers
  action_srv_fibonacci_ = rclcpp_action::create_server<example_interfaces::action::Fibonacci>(
    this,
    "fibonacci",
    [this](const rclcpp_action::GoalUUID & uuid, std::shared_ptr<const example_interfaces::action::Fibonacci::Goal> goal) {
      return this->on_fibonacci_goal(uuid, goal);
    },
    [this](std::shared_ptr<rclcpp_action::ServerGoalHandle<example_interfaces::action::Fibonacci>> goal_handle) {
      return this->on_fibonacci_cancel(goal_handle);
    },
    [this](std::shared_ptr<rclcpp_action::ServerGoalHandle<example_interfaces::action::Fibonacci>> goal_handle) {
      this->on_fibonacci_accepted(goal_handle);
    });

  // Create action clients
  action_cli_navigate_ = rclcpp_action::create_client<nav2_msgs::action::NavigateToPose>(this, "navigate");
}
