// GENERATED FILE — do not edit. Regenerated from NoDL by nodl_generator_cpp.
#pragma once

#include <memory>

#include <nodl_runtime_cpp/lifecycle_node.hpp>
#include <nodl_runtime_cpp/mutex_protected.hpp>
#include <nodl_runtime_cpp/parameter_values.hpp>
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

  /// Called after `params_` takes the values of an accepted parameter change.
  /// Only while the node is active.
  /// Runs during parameter validation, before the change is committed, so read `params` instead of `get_parameter()`.
  /// It cannot reject a change and must not block.
  virtual void on_parameters_changed(const my_node_base::Params & params)
  {
    (void)params;
  }

  /// Store the current parameter values in `params_`, without calling `on_parameters_changed`.
  void refresh_parameters() final;

  /// Follow parameter changes in `params_`, and call `on_parameters_changed` for each.
  void start_parameter_updates() final;

  /// Stop following parameter changes.
  void stop_parameter_updates() final;
};
