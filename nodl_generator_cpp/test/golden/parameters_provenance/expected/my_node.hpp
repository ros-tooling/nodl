// GENERATED FILE — do not edit. Regenerated from NoDL by nodl_generator_cpp.
#pragma once

#include <memory>

#include <rclcpp/rclcpp.hpp>
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
};
