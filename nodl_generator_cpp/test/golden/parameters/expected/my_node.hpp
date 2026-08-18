// GENERATED FILE — do not edit. Regenerated from NoDL by nodl_generator_cpp.
#pragma once

#include <memory>

#include <rclcpp/rclcpp.hpp>
#include <std_msgs/msg/string.hpp>
#include "my_node_parameters.hpp"

class MyNodeBase : public rclcpp::Node
{
public:
  explicit MyNodeBase(const rclcpp::NodeOptions & options = rclcpp::NodeOptions{});

  virtual ~MyNodeBase() = default;

protected:

  // --- Parameters ---
  my_node::ParamListener param_listener_;
  my_node::Params params_;

  // --- Publishers ---
  rclcpp::Publisher<std_msgs::msg::String>::SharedPtr pub_status_;
};
