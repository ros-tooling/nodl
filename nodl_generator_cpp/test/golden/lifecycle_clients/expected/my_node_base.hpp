// GENERATED FILE — do not edit. Regenerated from NoDL by nodl_generator_cpp.
#pragma once

#include <memory>

#include <example_interfaces/srv/add_two_ints.hpp>
#include <nav2_msgs/action/navigate_to_pose.hpp>
#include <nodl_runtime_cpp/active_only_action_client.hpp>
#include <nodl_runtime_cpp/active_only_client.hpp>
#include <nodl_runtime_cpp/lifecycle_node.hpp>
#include <rclcpp_action/rclcpp_action.hpp>

class MyNodeBase : public nodl_runtime_cpp::LifecycleNode
{
public:
  explicit MyNodeBase(const rclcpp::NodeOptions & options = rclcpp::NodeOptions{});

  virtual ~MyNodeBase() = default;

protected:

  // --- Service clients ---
  nodl_runtime_cpp::ActiveOnlyClient<example_interfaces::srv::AddTwoInts>::SharedPtr cli_add_;

  // --- Action clients ---
  nodl_runtime_cpp::ActiveOnlyActionClient<nav2_msgs::action::NavigateToPose>::SharedPtr action_cli_navigate_;
};
