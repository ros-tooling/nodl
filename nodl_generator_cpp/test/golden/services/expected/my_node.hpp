// GENERATED FILE — do not edit. Regenerated from NoDL by nodl_generator_cpp.
#pragma once

#include <memory>

#include <rclcpp/rclcpp.hpp>
#include <std_srvs/srv/set_bool.hpp>
#include <std_srvs/srv/trigger.hpp>

class MyNodeBase : public rclcpp::Node
{
public:
  explicit MyNodeBase(const rclcpp::NodeOptions & options = rclcpp::NodeOptions{});

  virtual ~MyNodeBase() = default;

protected:

  // --- Service server callbacks ---
  virtual void on_trigger(std_srvs::srv::Trigger::Request::SharedPtr request, std_srvs::srv::Trigger::Response::SharedPtr response) = 0;

  // --- Service clients ---
  rclcpp::Client<std_srvs::srv::SetBool>::SharedPtr cli_set_bool_;

private:

  // --- Service servers ---
  rclcpp::Service<std_srvs::srv::Trigger>::SharedPtr srv_trigger_;
};
