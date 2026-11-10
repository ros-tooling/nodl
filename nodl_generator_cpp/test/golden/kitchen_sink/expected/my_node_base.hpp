// GENERATED FILE — do not edit. Regenerated from NoDL by nodl_generator_cpp.
#pragma once

#include <memory>

#include <example_interfaces/action/fibonacci.hpp>
#include <geometry_msgs/msg/twist.hpp>
#include <nav2_msgs/action/navigate_to_pose.hpp>
#include <nodl_runtime_cpp/mutex_protected.hpp>
#include <rclcpp/rclcpp.hpp>
#include <rclcpp_action/rclcpp_action.hpp>
#include <std_msgs/msg/string.hpp>
#include <std_srvs/srv/set_bool.hpp>
#include <std_srvs/srv/trigger.hpp>
#include "my_node_base_parameters.hpp"

class MyNodeBase : public rclcpp::Node
{
public:
  explicit MyNodeBase(const rclcpp::NodeOptions & options = rclcpp::NodeOptions{});

  virtual ~MyNodeBase() = default;

private:
  // Declared before params_, which is initialized from it.
  my_node_base::ParamListener param_listener_;

protected:

  // --- Parameters ---
  /// The latest parameter values.
  /// Read them through `params_.lock()`, and copy rather than bind a reference beyond the guard.
  nodl_runtime_cpp::MutexProtected<my_node_base::Params> params_;

  /// Read-only access to the parameter listener, for `get_params()`, `try_get_params()`, `try_update_params()` and `is_old()`.
  const my_node_base::ParamListener & param_listener() const
  {
    return param_listener_;
  }

  /// Called after `params_` takes the values of an accepted parameter change.
  /// Runs during parameter validation, before the change is committed, so read `params` instead of `get_parameter()`.
  /// It cannot reject a change and must not block.
  virtual void on_parameters_changed(const my_node_base::Params & params)
  {
    (void)params;
  }

  // --- Publishers ---
  rclcpp::Publisher<std_msgs::msg::String>::SharedPtr pub_status_;

  // --- Subscription callbacks ---
  virtual void on_cmd_vel(geometry_msgs::msg::Twist::ConstSharedPtr msg) = 0;

  // --- Service server callbacks ---
  virtual void on_trigger(std_srvs::srv::Trigger::Request::SharedPtr request, std_srvs::srv::Trigger::Response::SharedPtr response) = 0;

  // --- Action server callbacks ---
  virtual rclcpp_action::GoalResponse on_fibonacci_goal(const rclcpp_action::GoalUUID & uuid, std::shared_ptr<const example_interfaces::action::Fibonacci::Goal> goal) = 0;
  virtual rclcpp_action::CancelResponse on_fibonacci_cancel(std::shared_ptr<rclcpp_action::ServerGoalHandle<example_interfaces::action::Fibonacci>> goal_handle) = 0;
  /// @brief Called when a goal is accepted.  Do not block in this callback;
  /// doing so prevents cancel requests from being processed.  Detach a thread
  /// for long-running work, e.g.:
  ///   std::thread{[goal_handle]() { /* execute */ }}.detach();
  virtual void on_fibonacci_accepted(std::shared_ptr<rclcpp_action::ServerGoalHandle<example_interfaces::action::Fibonacci>> goal_handle) = 0;

  // --- Service clients ---
  rclcpp::Client<std_srvs::srv::SetBool>::SharedPtr cli_set_bool_;

  // --- Action clients ---
  rclcpp_action::Client<nav2_msgs::action::NavigateToPose>::SharedPtr action_cli_navigate_;

private:

  // --- Subscriptions ---
  rclcpp::Subscription<geometry_msgs::msg::Twist>::SharedPtr sub_cmd_vel_;

  // --- Service servers ---
  rclcpp::Service<std_srvs::srv::Trigger>::SharedPtr srv_trigger_;

  // --- Action servers ---
  rclcpp_action::Server<example_interfaces::action::Fibonacci>::SharedPtr action_srv_fibonacci_;
};
