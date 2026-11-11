// SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
// SPDX-License-Identifier: Apache-2.0
#pragma once

#include <cstddef>
#include <exception>
#include <functional>
#include <memory>
#include <stdexcept>
#include <utility>
#include <vector>

#include "lifecycle_msgs/msg/state.hpp"
#include "nodl_runtime_cpp/goal_tracker.hpp"
#include "rclcpp/logging.hpp"
#include "rclcpp/version.h"
#include "rclcpp_action/server.hpp"
#include "rclcpp_lifecycle/lifecycle_node.hpp"

namespace nodl_runtime_cpp
{

/// A lifecycle node with sealed transition callbacks, optional `handle_*` hooks and an activation registry.
/**
 * Derive it and override the `handle_*` hooks that need custom behavior.
 * The `on_*` transition callbacks are `final`, and run the standard activation and deactivation of
 * `rclcpp_lifecycle::LifecycleNode` around the hooks.
 *
 * The registry (`manage` and `add_activation_slot`) creates endpoints when the node activates and destroys them when it deactivates.
 * Register from the constructor, in the order the endpoints must be created.
 * See the `nodl_runtime_cpp` overview for the order on each transition.
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

  /// Creates the slots, runs the standard activation, then runs `handle_activate`.
  /**
   * When a slot or `handle_activate` throws, or does not return SUCCESS, the created slots are destroyed.
   * A result other than SUCCESS is returned, and an exception propagates.
   */
  CallbackReturn on_activate(const rclcpp_lifecycle::State & previous_state) final
  {
    deactivate_hook_ran_ = false;
    activate_slots();
    const auto activated = rclcpp_lifecycle::LifecycleNode::on_activate(previous_state);
    if (CallbackReturn::SUCCESS != activated) {
      deactivate_slots();
      return activated;
    }
    CallbackReturn result;
    try {
      result = handle_activate(previous_state);
    } catch (...) {
      deactivate_slots();
      throw;
    }
    if (CallbackReturn::SUCCESS != result) {
      rclcpp_lifecycle::LifecycleNode::on_deactivate(previous_state);
      deactivate_slots();
    }
    return result;
  }

  /// Runs `handle_deactivate`, then the standard deactivation and the slot destruction if the hook returned SUCCESS.
  CallbackReturn on_deactivate(const rclcpp_lifecycle::State & previous_state) final
  {
    deactivate_hook_ran_ = true;
    const auto result = handle_deactivate(previous_state);
    if (CallbackReturn::SUCCESS != result) {
      deactivate_hook_ran_ = false;
      return result;
    }
    const auto deactivated = rclcpp_lifecycle::LifecycleNode::on_deactivate(previous_state);
    deactivate_slots();
    return deactivated;
  }

  /// Runs `handle_cleanup`.
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
  /// Registers a pair of functions that create and destroy an endpoint with the node's activation.
  /**
   * `create` runs at activation, in registration order.
   * `destroy` runs in reverse registration order at deactivation, shutdown and error, and when a later slot fails to activate.
   * It must be safe to call when `create` has not run, it must not throw, and it does not run when the node is destroyed.
   * A `create` that throws rolls back the slots created before it.
   *
   * \throws std::logic_error When called while the node is activating or active.
   */
  void add_activation_slot(std::function<void()> create, std::function<void()> destroy)
  {
    if (slots_locked_) {
      throw std::logic_error("slots can be registered only while the node is not active");
    }
    slots_.push_back({std::move(create), std::move(destroy)});
  }

  /// Registers a slot that assigns `member` with the result of `make` at activation, and resets it at destruction.
  /**
   * The member is null while the node is not active, and the node must outlive the registration, so register from the constructor.
   * The creator's result must convert to the member's type.
   *
   * \tparam EntityT Type of the endpoint, such as `rclcpp::Subscription<MessageT>`.
   * \tparam MakeT Callable that returns the endpoint as a `std::shared_ptr`.
   * \throws std::logic_error When called while the node is activating or active.
   */
  template <typename EntityT, typename MakeT>
  void manage(std::shared_ptr<EntityT> & member, MakeT make)
  {
    add_activation_slot([&member, make = std::move(make)] { member = make(); }, [&member] { member.reset(); });
  }

  /// Registers an action server slot that ends the active goals before it destroys the server.
  /**
   * `make` receives the `GoalTracker` of the server, and returns the server created with `rclcpp_action::create_server`.
   * Pass `tracker.accepted(callback)` as the accepted callback of the server.
   * At deactivation, shutdown and error, each recorded goal that is still active ends with a default-constructed result
   * before the server is destroyed, after `handle_deactivate` has run.
   * See `GoalTracker` for how each goal state ends.
   *
   * \tparam ActionT Action type.
   * \tparam MakeT Callable that takes a `GoalTracker<ActionT> &` and returns the server as a `std::shared_ptr`.
   * \throws std::logic_error When called while the node is activating or active.
   */
  template <typename ActionT, typename MakeT>
  void manage_action_server(typename rclcpp_action::Server<ActionT>::SharedPtr & member, MakeT make)
  {
    auto tracker = std::make_shared<GoalTracker<ActionT>>();
    add_activation_slot(
      [&member, tracker, make = std::move(make)] {
        tracker->open();
        member = make(*tracker);
      },
      [&member, tracker] {
        tracker->end_all();
        member.reset();
      });
  }

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

  /// Called on the shutdown transition, after the endpoints are destroyed.
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
  struct Slot
  {
    std::function<void()> create;
    std::function<void()> destroy;
  };

  /// Runs the deactivation that shutdown and error need: the hook when the node is active, then the slots.
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
    for (const auto & slot : slots_) {
      try {
        slot.create();
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

  /// Wakes the executors that wait on this node, so they release the destroyed endpoints they still hold.
  /// A node that no executor is spinning keeps them until its next spin.
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
  std::size_t active_slots_ = 0;
  /// True from the start of the activation of the slots until they are destroyed.
  bool slots_locked_ = false;
  /// True when `handle_deactivate` ran for the current active period.
  bool deactivate_hook_ran_ = false;
};

}  // namespace nodl_runtime_cpp
