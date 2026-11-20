// SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
// SPDX-License-Identifier: Apache-2.0
#pragma once

#include <algorithm>
#include <cstddef>
#include <cstdint>
#include <exception>
#include <functional>
#include <memory>
#include <stdexcept>
#include <utility>
#include <vector>

#include "lifecycle_msgs/msg/state.hpp"
#include "rclcpp/logging.hpp"
#include "rclcpp/version.h"
#include "rclcpp_lifecycle/lifecycle_node.hpp"

namespace nodl_runtime_cpp
{

template <typename EntityT>
class Managed;

/// A lifecycle node with sealed transition callbacks, optional `handle_*` hooks and an activation registry.
/**
 * Derive it and override the `handle_*` hooks that need custom behavior.
 * The `on_*` transition callbacks are `final`, and run the standardized lifecycle management for endpoints.
 *
 * The registry creates endpoints when the node activates and destroys them when it deactivates.
 * Declare a `Managed` member for each endpoint, in the order the endpoints must be created.
 * `add_activation_slot` is the underlying primitive.
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

  /// Move node from inactive to active. Runs the standard activation, creates the slots, then calls `handle_activate`.
  /**
   * When `handle_activate` does not return SUCCESS or throws, the slots are destroyed and the standard deactivation runs.
   * A result other than SUCCESS is returned, and an exception propagates.
   * A slot that throws rolls back the slots created before it, and the exception propagates.
   */
  CallbackReturn on_activate(const rclcpp_lifecycle::State & previous_state) final
  {
    deactivate_hook_ran_ = false;
    const auto base_result = rclcpp_lifecycle::LifecycleNode::on_activate(previous_state);
    if (CallbackReturn::SUCCESS != base_result) {
      return base_result;
    }
    activate_slots();
    CallbackReturn hook_result;
    try {
      hook_result = handle_activate(previous_state);
    } catch (...) {
      deactivate_slots();
      throw;
    }
    if (CallbackReturn::SUCCESS != hook_result) {
      deactivate_slots();
      rclcpp_lifecycle::LifecycleNode::on_deactivate(previous_state);
    }
    return hook_result;
  }

  /// Move node from active to inactive. Calls `handle_deactivate`, then destroys the slots if it succeeded.
  CallbackReturn on_deactivate(const rclcpp_lifecycle::State & previous_state) final
  {
    deactivate_hook_ran_ = true;
    const auto hook_result = handle_deactivate(previous_state);
    if (CallbackReturn::SUCCESS != hook_result) {
      deactivate_hook_ran_ = false;
      return hook_result;
    }
    deactivate_slots();
    return rclcpp_lifecycle::LifecycleNode::on_deactivate(previous_state);
  }

  /// Move node from inactive to unconfigured. Calls `handle_cleanup`.
  CallbackReturn on_cleanup(const rclcpp_lifecycle::State & previous_state) final
  {
    return handle_cleanup(previous_state);
  }

  /// Ends the active state, then runs `handle_shutdown`.
  /**
   * From the active state this runs `handle_deactivate`, destroys the slots and runs the standard deactivation first.
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
  /// Opaque identifier of a registered slot.
  using SlotId = std::uint64_t;

  /// Registers a pair of functions that create and destroy an endpoint with the node's activation.
  /**
   * `create` runs at activation in registration order, after the standard activation and before `handle_activate`.
   * `destroy` runs in reverse registration order at deactivation, shutdown and error,
   * and when `handle_activate` fails or a later slot throws.
   * `destroy` runs only for a slot whose `create` returned, it must not throw, and it does not run when the node is destroyed.
   * A `create` that throws must leave nothing behind.
   *
   * \return The id of the slot.
   * \throws std::logic_error When called while the node is activating or active.
   */
  SlotId add_activation_slot(std::function<void()> create, std::function<void()> destroy)
  {
    if (slots_locked_) {
      throw std::logic_error("slots can be registered only while the node is not active");
    }
    const SlotId id = next_slot_id_++;
    slots_.push_back({id, std::move(create), std::move(destroy)});
    return id;
  }

  /// Called on the configure transition.
  virtual CallbackReturn handle_configure(const rclcpp_lifecycle::State & /*previous_state*/)
  {
    return CallbackReturn::SUCCESS;
  }

  /// Called on the activate transition, after the standard activation and the creation of the slots.
  /**
   * FAILURE leaves the node inactive, and ERROR runs `handle_error`.
   */
  virtual CallbackReturn handle_activate(const rclcpp_lifecycle::State & /*previous_state*/)
  {
    return CallbackReturn::SUCCESS;
  }

  /// Called on the deactivate transition, before the slots are destroyed.
  /**
   * FAILURE leaves the node active, and ERROR runs `handle_error`.
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

  /// Called on the shutdown transition, after the slots are destroyed.
  virtual CallbackReturn handle_shutdown(const rclcpp_lifecycle::State & /*previous_state*/)
  {
    return CallbackReturn::SUCCESS;
  }

  /// Called on the error transition, after the slots are destroyed.
  /**
   * SUCCESS takes the node to the unconfigured state, and any other result finalizes it.
   */
  virtual CallbackReturn handle_error(const rclcpp_lifecycle::State & /*previous_state*/)
  {
    return CallbackReturn::SUCCESS;
  }

private:
  template <typename EntityT>
  friend class Managed;

  struct Slot
  {
    SlotId id;
    std::function<void()> create;
    std::function<void()> destroy;
  };

  /// Unregisters a slot without calling `destroy`, keeping the order of the others.
  /**
   * \throws std::logic_error When called while the node is activating or active.
   */
  void remove_activation_slot(SlotId id)
  {
    if (slots_locked_) {
      throw std::logic_error("slots can be removed only while the node is not active");
    }
    discard_activation_slot(id);
  }

  /// Unregisters a slot at any time, and counts it out of the created slots if it was created.
  void discard_activation_slot(SlotId id) noexcept
  {
    const auto it = std::find_if(slots_.begin(), slots_.end(), [id](const Slot & slot) { return id == slot.id; });
    if (slots_.end() == it) {
      return;
    }
    if (static_cast<std::size_t>(it - slots_.begin()) < active_slots_) {
      --active_slots_;
    }
    slots_.erase(it);
  }

  /// Runs the deactivation that shutdown and error need: the authored hook if the node is active, then the slots.
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
    deactivate_slots();
    rclcpp_lifecycle::LifecycleNode::on_deactivate(previous_state);
  }

  /// Creates the slots in order, and destroys the created ones in reverse if one throws.
  void activate_slots()
  {
    slots_locked_ = true;
    while (active_slots_ < slots_.size()) {
      try {
        slots_[active_slots_].create();
      } catch (...) {
        deactivate_slots();
        throw;
      }
      ++active_slots_;
    }
  }

  /// Destroys the created slots in reverse, and does nothing when the slots are not active.
  void deactivate_slots()
  {
    if (!slots_locked_) {
      return;
    }
    const bool destroyed_any = 0 != active_slots_;
    while (0 != active_slots_) {
      --active_slots_;
      try {
        slots_[active_slots_].destroy();
      } catch (const std::exception & e) {
        RCLCPP_ERROR(get_logger(), "Destroying an activation slot failed: %s", e.what());
      }
    }
    slots_locked_ = false;
    if (destroyed_any) {
      wake_executors();
    }
  }

  /// Wakes the executors that wait on this node.
  void wake_executors()
  {
    try {
#if RCLCPP_VERSION_MAJOR >= 21
      get_node_base_interface()->trigger_notify_guard_condition();
#else
      get_node_base_interface()->get_notify_guard_condition().trigger();
#endif
    } catch (const std::exception & e) {
      RCLCPP_ERROR(get_logger(), "Waking the executor failed: %s", e.what());
    }
  }

  std::vector<Slot> slots_;
  SlotId next_slot_id_ = 0;
  std::size_t active_slots_ = 0;
  /// True from the start of the activation of the slots until they are destroyed.
  bool slots_locked_ = false;
  /// True when `handle_deactivate` ran for the current active period.
  bool deactivate_hook_ran_ = false;
};

}  // namespace nodl_runtime_cpp
