// GENERATED FILE — do not edit. Regenerated from NoDL by nodl_generator_cpp.
#pragma once

#include <memory>

#include <nodl_runtime_cpp/mutex_protected.hpp>
#include <rclcpp/rclcpp.hpp>
#include <std_msgs/msg/string.hpp>
#include "my_node_base_parameters.hpp"

namespace my_pkg::nodes
{
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
};

}  // namespace my_pkg::nodes
