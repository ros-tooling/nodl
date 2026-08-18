// GENERATED FILE — do not edit. Regenerated from NoDL by nodl_generator_cpp.
#pragma once

#include <memory>

#include <example_interfaces/action/fibonacci.hpp>
#include <nav2_msgs/action/navigate_to_pose.hpp>
#include <rclcpp/rclcpp.hpp>
#include <rclcpp_action/rclcpp_action.hpp>

class MyNodeBase : public rclcpp::Node
{
public:
  explicit MyNodeBase(const rclcpp::NodeOptions & options = rclcpp::NodeOptions{});

  virtual ~MyNodeBase() = default;

protected:

  // --- Action server callbacks ---
  virtual rclcpp_action::GoalResponse on_fibonacci_goal(const rclcpp_action::GoalUUID & uuid, std::shared_ptr<const example_interfaces::action::Fibonacci::Goal> goal) = 0;
  virtual rclcpp_action::CancelResponse on_fibonacci_cancel(std::shared_ptr<rclcpp_action::ServerGoalHandle<example_interfaces::action::Fibonacci>> goal_handle) = 0;
  /// @brief Called when a goal is accepted.  Do not block in this callback;
  /// doing so prevents cancel requests from being processed.  Detach a thread
  /// for long-running work, e.g.:
  ///   std::thread{[goal_handle]() { /* execute */ }}.detach();
  virtual void on_fibonacci_accepted(std::shared_ptr<rclcpp_action::ServerGoalHandle<example_interfaces::action::Fibonacci>> goal_handle) = 0;

  // --- Action clients ---
  rclcpp_action::Client<nav2_msgs::action::NavigateToPose>::SharedPtr action_cli_navigate_;

private:

  // --- Action servers ---
  rclcpp_action::Server<example_interfaces::action::Fibonacci>::SharedPtr action_srv_fibonacci_;
};
