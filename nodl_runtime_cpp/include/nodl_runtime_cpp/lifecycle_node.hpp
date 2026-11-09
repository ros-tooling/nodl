// SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
// SPDX-License-Identifier: Apache-2.0
#pragma once

#include <memory>
#include <utility>

#include "nodl_runtime_cpp/gate.hpp"
#include "rclcpp_lifecycle/lifecycle_node.hpp"

namespace nodl_runtime_cpp
{

/// A lifecycle node with sealed transition callbacks and optional `handle_*` hooks.
/**
 * Derive it and override the `handle_*` hooks that need custom behavior.
 * The `on_*` transition callbacks are `final`, and run the standard activation and deactivation of
 * `rclcpp_lifecycle::LifecycleNode` around the hooks.
 * See the `nodl_runtime_cpp` overview for the order on each transition.
 * The node owns an activation gate, which `gate()` exposes to subclasses.
 */
class LifecycleNode : public rclcpp_lifecycle::LifecycleNode
{
public:
  using CallbackReturn = rclcpp_lifecycle::node_interfaces::LifecycleNodeInterface::CallbackReturn;

  /// Construct the node and register its activation gate.
  /**
   * \param[in] args Arguments of a `rclcpp_lifecycle::LifecycleNode` constructor.
   */
  template <typename... Args>
  explicit LifecycleNode(Args &&... args)
  : rclcpp_lifecycle::LifecycleNode(std::forward<Args>(args)...)
  {
    add_managed_entity(gate_);
  }

  /// Runs `handle_configure`.
  CallbackReturn on_configure(const rclcpp_lifecycle::State & previous_state) final
  {
    return handle_configure(previous_state);
  }

  /// Runs the standard activation, then `handle_activate`.
  /**
   * When `handle_activate` does not return SUCCESS, runs the standard deactivation and returns its result.
   */
  CallbackReturn on_activate(const rclcpp_lifecycle::State & previous_state) final
  {
    const auto activated = rclcpp_lifecycle::LifecycleNode::on_activate(previous_state);
    if (CallbackReturn::SUCCESS != activated) {
      return activated;
    }
    const auto result = handle_activate(previous_state);
    if (CallbackReturn::SUCCESS != result) {
      rclcpp_lifecycle::LifecycleNode::on_deactivate(previous_state);
    }
    return result;
  }

  /// Runs `handle_deactivate`, then the standard deactivation if the hook returned SUCCESS.
  CallbackReturn on_deactivate(const rclcpp_lifecycle::State & previous_state) final
  {
    const auto result = handle_deactivate(previous_state);
    if (CallbackReturn::SUCCESS != result) {
      return result;
    }
    return rclcpp_lifecycle::LifecycleNode::on_deactivate(previous_state);
  }

  /// Runs `handle_cleanup`.
  CallbackReturn on_cleanup(const rclcpp_lifecycle::State & previous_state) final
  {
    return handle_cleanup(previous_state);
  }

  /// Runs the standard deactivation, then `handle_shutdown`.
  CallbackReturn on_shutdown(const rclcpp_lifecycle::State & previous_state) final
  {
    rclcpp_lifecycle::LifecycleNode::on_deactivate(previous_state);
    return handle_shutdown(previous_state);
  }

  /// Runs the standard deactivation, then `handle_error`.
  CallbackReturn on_error(const rclcpp_lifecycle::State & previous_state) final
  {
    rclcpp_lifecycle::LifecycleNode::on_deactivate(previous_state);
    return handle_error(previous_state);
  }

protected:
  /// The activation gate, open while the node is active.
  /**
   * It opens in the standard activation, so it is already open in `handle_activate`.
   */
  GatePtr gate() const
  {
    return gate_;
  }

  /// Called on the configure transition.
  virtual CallbackReturn handle_configure(const rclcpp_lifecycle::State & /*previous_state*/)
  {
    return CallbackReturn::SUCCESS;
  }

  /// Called on the activate transition, after the standard activation.
  /**
   * The gate is already open.
   * A result other than SUCCESS leaves the node inactive.
   */
  virtual CallbackReturn handle_activate(const rclcpp_lifecycle::State & /*previous_state*/)
  {
    return CallbackReturn::SUCCESS;
  }

  /// Called on the deactivate transition, before the standard deactivation.
  /**
   * A result other than SUCCESS leaves the node active.
   */
  virtual CallbackReturn handle_deactivate(const rclcpp_lifecycle::State & /*previous_state*/)
  {
    return CallbackReturn::SUCCESS;
  }

  /// Called on the cleanup transition.
  virtual CallbackReturn handle_cleanup(const rclcpp_lifecycle::State & /*previous_state*/)
  {
    return CallbackReturn::SUCCESS;
  }

  /// Called on the shutdown transition, after the standard deactivation.
  virtual CallbackReturn handle_shutdown(const rclcpp_lifecycle::State & /*previous_state*/)
  {
    return CallbackReturn::SUCCESS;
  }

  /// Called on the error transition, after the standard deactivation.
  /**
   * SUCCESS takes the node to the unconfigured state, and any other result finalizes it.
   */
  virtual CallbackReturn handle_error(const rclcpp_lifecycle::State & /*previous_state*/)
  {
    return CallbackReturn::SUCCESS;
  }

private:
  std::shared_ptr<Gate> gate_ = std::make_shared<Gate>();
};

}  // namespace nodl_runtime_cpp
