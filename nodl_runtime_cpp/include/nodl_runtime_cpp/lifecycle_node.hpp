// SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
// SPDX-License-Identifier: Apache-2.0
#ifndef NODL_RUNTIME_CPP__LIFECYCLE_NODE_HPP_
#define NODL_RUNTIME_CPP__LIFECYCLE_NODE_HPP_

#include "rclcpp_lifecycle/lifecycle_node.hpp"

namespace nodl_runtime_cpp
{

/// A lifecycle node whose transitions keep their standard behavior and are extended through hooks.
/**
 * `rclcpp_lifecycle::LifecycleNode` activates and deactivates its lifecycle publishers and other managed entities
 * in its default `on_activate` and `on_deactivate`, so a subclass that overrides them without calling the base class
 * leaves those entities inactive.
 * This class seals `on_configure`, `on_activate`, `on_deactivate`, `on_cleanup`, `on_shutdown` and `on_error`,
 * and calls the optional `handle_*` hooks instead.
 * Each hook defaults to SUCCESS.
 *
 * | Transition | Order |
 * |---|---|
 * | configure | `handle_configure` only |
 * | activate | standard activation, then `handle_activate`, and a non-SUCCESS result runs the standard deactivation |
 * | deactivate | `handle_deactivate`, then the standard deactivation if it returned SUCCESS |
 * | cleanup | `handle_cleanup` only |
 * | shutdown | standard deactivation, then `handle_shutdown` |
 * | error | standard deactivation, then `handle_error` |
 *
 * The standard activation and deactivation are those of `rclcpp_lifecycle::LifecycleNode`.
 * Only they reach managed entities, so entities added with `add_managed_entity` do not receive configure or cleanup.
 * A hook that throws is turned into ERROR by `rclcpp_lifecycle`, which runs `on_error`,
 * and the node ends unconfigured when `handle_error` returns SUCCESS.
 */
class LifecycleNode : public rclcpp_lifecycle::LifecycleNode
{
public:
  using rclcpp_lifecycle::LifecycleNode::LifecycleNode;
  using CallbackReturn = rclcpp_lifecycle::node_interfaces::LifecycleNodeInterface::CallbackReturn;

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
  /// Called on the configure transition.
  virtual CallbackReturn handle_configure(const rclcpp_lifecycle::State & /*previous_state*/)
  {
    return CallbackReturn::SUCCESS;
  }

  /// Called on the activate transition, after the standard activation.
  /**
   * Lifecycle publishers are already active.
   * A result other than SUCCESS leaves the node inactive, with the standard deactivation run.
   */
  virtual CallbackReturn handle_activate(const rclcpp_lifecycle::State & /*previous_state*/)
  {
    return CallbackReturn::SUCCESS;
  }

  /// Called on the deactivate transition, before the standard deactivation.
  /**
   * A result other than SUCCESS leaves the node active, and skips the standard deactivation.
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
};

}  // namespace nodl_runtime_cpp

#endif  // NODL_RUNTIME_CPP__LIFECYCLE_NODE_HPP_
