// GENERATED FILE — do not edit. Regenerated from NoDL by nodl_generator_cpp.
#pragma once

#include <memory>

#include <nodl_runtime_cpp/lifecycle_node.hpp>
#include <nodl_runtime_cpp/mutex_protected.hpp>
#include "my_node_base_parameters.hpp"

class MyNodeBase : public nodl_runtime_cpp::LifecycleNode
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
};
