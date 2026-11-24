// GENERATED FILE — do not edit. Regenerated from NoDL by nodl_generator_cpp.
#pragma once

#include <memory>

#include <geometry_msgs/msg/twist.hpp>
#include <nodl_runtime_cpp/lifecycle_node.hpp>
#include <nodl_runtime_cpp/managed.hpp>
#include <std_msgs/msg/string.hpp>
#include <std_srvs/srv/trigger.hpp>

class MyNodeBase : public nodl_runtime_cpp::LifecycleNode
{
public:
  explicit MyNodeBase(const rclcpp::NodeOptions & options = rclcpp::NodeOptions{});

  virtual ~MyNodeBase() = default;

protected:

  // --- Publishers ---
  rclcpp_lifecycle::LifecyclePublisher<std_msgs::msg::String>::SharedPtr pub_status_;

  // --- Subscription callbacks ---
  virtual void on_cmd_vel(geometry_msgs::msg::Twist::ConstSharedPtr msg) = 0;
  virtual void on_latched(std_msgs::msg::String::ConstSharedPtr msg) = 0;

  // --- Service server callbacks ---
  virtual void on_trigger(std_srvs::srv::Trigger::Request::SharedPtr request, std_srvs::srv::Trigger::Response::SharedPtr response) = 0;

private:

  // --- Subscriptions ---
  nodl_runtime_cpp::Managed<rclcpp::Subscription<geometry_msgs::msg::Twist>> sub_cmd_vel_;
  nodl_runtime_cpp::Managed<rclcpp::Subscription<std_msgs::msg::String>> sub_latched_;

  // --- Service servers ---
  nodl_runtime_cpp::Managed<rclcpp::Service<std_srvs::srv::Trigger>> srv_trigger_;
};
