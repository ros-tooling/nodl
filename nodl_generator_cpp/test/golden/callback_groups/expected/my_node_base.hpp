// GENERATED FILE — do not edit. Regenerated from NoDL by nodl_generator_cpp.
#pragma once

#include <memory>

#include <rclcpp/rclcpp.hpp>
#include <std_msgs/msg/empty.hpp>
#include <std_srvs/srv/trigger.hpp>

class MyNodeBase : public rclcpp::Node
{
public:
  explicit MyNodeBase(const rclcpp::NodeOptions & options = rclcpp::NodeOptions{});

  virtual ~MyNodeBase() = default;

protected:

  // --- Subscription callbacks ---
  virtual void on_work(std_msgs::msg::Empty::ConstSharedPtr msg) = 0;

  // --- Service server callbacks ---
  virtual void on_status(std_srvs::srv::Trigger::Request::SharedPtr request, std_srvs::srv::Trigger::Response::SharedPtr response) = 0;

private:

  // Retain groups until after their endpoints are destroyed.
  rclcpp::CallbackGroup::SharedPtr nodl_callback_group_control_;
  rclcpp::CallbackGroup::SharedPtr nodl_callback_group_processing_;

  // --- Subscriptions ---
  rclcpp::Subscription<std_msgs::msg::Empty>::SharedPtr sub_work_;

  // --- Service servers ---
  rclcpp::Service<std_srvs::srv::Trigger>::SharedPtr srv_status_;
};
