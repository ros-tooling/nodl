// GENERATED FILE — do not edit. Regenerated from NoDL by nodl_generator_cpp.
#pragma once

#include <memory>

#include <geometry_msgs/msg/twist.hpp>
#include <nav2_msgs/action/navigate_to_pose.hpp>
#include <nodl_runtime_cpp/gated.hpp>
#include <nodl_runtime_cpp/lifecycle_node.hpp>
#include <nodl_runtime_cpp/managed.hpp>
#include <rclcpp_action/rclcpp_action.hpp>
#include <std_srvs/srv/set_bool.hpp>

class MyNodeBase : public nodl_runtime_cpp::LifecycleNode
{
public:
  explicit MyNodeBase(const rclcpp::NodeOptions & options = rclcpp::NodeOptions{});

  virtual ~MyNodeBase() = default;

protected:

  // --- Subscription callbacks ---
  virtual void on_cmd_vel(geometry_msgs::msg::Twist::ConstSharedPtr msg) = 0;

  // --- Service clients ---
  nodl_runtime_cpp::Gated<rclcpp::Client<std_srvs::srv::SetBool>> cli_set_bool_;

  // --- Action clients ---
  nodl_runtime_cpp::Gated<rclcpp_action::Client<nav2_msgs::action::NavigateToPose>> action_cli_navigate_;

private:

  // --- Subscriptions ---
  nodl_runtime_cpp::Managed<rclcpp::Subscription<geometry_msgs::msg::Twist>> sub_cmd_vel_;
};
