// SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
// SPDX-License-Identifier: Apache-2.0
#pragma once

#include <exception>

#include "lifecycle_msgs/msg/state.hpp"
#include "rclcpp/logging.hpp"
#include "rclcpp_lifecycle/lifecycle_node.hpp"

namespace nodl_runtime_cpp
{

/// A lifecycle node with sealed transition callbacks and optional `handle_*` hooks.
/**
 * Derive it and override the `handle_*` hooks that need custom behavior.
 * The `on_*` transition callbacks are `final`, and run the standardized lifecycle management for endpoints.
 *
 * See the `nodl_runtime_cpp` overview for the order on each transition.
 */
class LifecycleNode : public rclcpp_lifecycle::LifecycleNode
{
public:
  using rclcpp_lifecycle::LifecycleNode::LifecycleNode;
  using CallbackReturn = rclcpp_lifecycle::node_interfaces::LifecycleNodeInterface::CallbackReturn;

  /// Move node from unconfigured to inactive. Calls `handle_configure`.
  CallbackReturn on_configure(const rclcpp_lifecycle::State & previous_state) final
  {
    return handle_configure(previous_state);
  }

  /// Move node from inactive to active. Calls `handle_activate`.
  CallbackReturn on_activate(const rclcpp_lifecycle::State & previous_state) final
  {
    const auto base_result = rclcpp_lifecycle::LifecycleNode::on_activate(previous_state);
    if (CallbackReturn::SUCCESS != base_result) {
      return base_result;
    }
    return handle_activate(previous_state);
  }

  /// Move node from active to inactive. Calls `handle_deactivate`.
  CallbackReturn on_deactivate(const rclcpp_lifecycle::State & previous_state) final
  {
    const auto handle_result = handle_deactivate(previous_state);
    if (CallbackReturn::SUCCESS != handle_result) {
      return handle_result;
    }
    return rclcpp_lifecycle::LifecycleNode::on_deactivate(previous_state);
  }

  /// Move node from inactive to unconfigured. Calls `handle_cleanup`.
  CallbackReturn on_cleanup(const rclcpp_lifecycle::State & previous_state) final
  {
    return handle_cleanup(previous_state);
  }

  /// Ends the active state, then runs `handle_shutdown`.
  /**
   * From the active state this runs `handle_deactivate` and runs the standard deactivation first.
   * A shutdown cannot be vetoed: the result of `handle_deactivate` is ignored and an exception from it is logged.
   */
  CallbackReturn on_shutdown(const rclcpp_lifecycle::State & previous_state) final
  {
    end_active_state(previous_state);
    return handle_shutdown(previous_state);
  }

  /// Ends the active state, then runs `handle_error`.
  /**
   * From the active state this runs `handle_deactivate` first, unless an exception from it caused the error,
   * then destroys the slots and runs the standard deactivation.
   * The result of `handle_deactivate` is ignored and an exception from it is logged.
   */
  CallbackReturn on_error(const rclcpp_lifecycle::State & previous_state) final
  {
    end_active_state(previous_state);
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
   * A result other than SUCCESS leaves the node inactive.
   */
  virtual CallbackReturn handle_activate(const rclcpp_lifecycle::State & /*previous_state*/)
  {
    return CallbackReturn::SUCCESS;
  }

  /// Called on the deactivate transition, before the endpoints are destroyed.
  /**
   * A result other than SUCCESS leaves the node active.
   * It also runs before shutdown and error from the active state, where the result is ignored.
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

  /// Called on the shutdown transition.
  virtual CallbackReturn handle_shutdown(const rclcpp_lifecycle::State & /*previous_state*/)
  {
    return CallbackReturn::SUCCESS;
  }

  /// Called on the error transition, after the endpoints are destroyed.
  /**
   * SUCCESS takes the node to the unconfigured state, and any other result finalizes it.
   */
  virtual CallbackReturn handle_error(const rclcpp_lifecycle::State & /*previous_state*/)
  {
    return CallbackReturn::SUCCESS;
  }

private:
  /// Runs the deactivation that shutdown and error need: the authored hook if the node is active.
  void end_active_state(const rclcpp_lifecycle::State & previous_state)
  {
    if (lifecycle_msgs::msg::State::PRIMARY_STATE_ACTIVE == previous_state.id() && !deactivate_hook_ran_) {
      deactivate_hook_ran_ = true;
      try {
        if (CallbackReturn::SUCCESS != handle_deactivate(previous_state)) {
          RCLCPP_WARN(get_logger(), "handle_deactivate did not succeed, and the shutdown continues");
        }
      } catch (const std::exception & e) {
        RCLCPP_ERROR(get_logger(), "handle_deactivate threw, and the shutdown continues: %s", e.what());
      } catch (...) {
        RCLCPP_ERROR(get_logger(), "handle_deactivate threw, and the shutdown continues");
      }
    }
    rclcpp_lifecycle::LifecycleNode::on_deactivate(previous_state);
  }

  /// True when `handle_deactivate` ran for the current active period.
  bool deactivate_hook_ran_ = false;
};

}  // namespace nodl_runtime_cpp
