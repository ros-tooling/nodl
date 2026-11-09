// SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
// SPDX-License-Identifier: Apache-2.0
#pragma once

#include <algorithm>
#include <memory>
#include <mutex>
#include <string>
#include <utility>
#include <vector>

#include "rclcpp/exceptions.hpp"
#include "rclcpp_action/create_server.hpp"
#include "rclcpp_action/server.hpp"
#include "rclcpp_action/server_goal_handle.hpp"
#include "rclcpp_lifecycle/managed_entity.hpp"

namespace nodl_runtime_cpp
{

/// An action server that rejects goals while inactive and ends its active goals at deactivation.
/**
 * The server is a managed entity, so register it with `add_managed_entity` and keep it alive.
 * It is inactive until the node activates.
 * `on_deactivate` becomes inactive first, then ends each recorded goal that is still active with a
 * default-constructed result: `abort()` for executing and deferred goals, `canceled()` for canceling goals.
 * A call that throws because the goal went terminal is skipped, and one that throws while the goal is still active
 * is retried once.
 * See the `nodl_runtime_cpp` overview for the goal state table and what workers must check.
 *
 * \tparam ActionT Action type.
 */
template <typename ActionT>
class ActiveOnlyActionServer : public rclcpp_lifecycle::SimpleManagedEntity
{
public:
  /// Shared pointer to the server, the type of a generated action server member.
  using SharedPtr = std::shared_ptr<ActiveOnlyActionServer>;
  /// Handle of an accepted goal.
  using GoalHandle = rclcpp_action::ServerGoalHandle<ActionT>;
  /// Decides whether a goal is accepted, as for `rclcpp_action::create_server`.
  using GoalCallback = typename rclcpp_action::Server<ActionT>::GoalCallback;
  /// Decides whether a goal is canceled, as for `rclcpp_action::create_server`.
  using CancelCallback = typename rclcpp_action::Server<ActionT>::CancelCallback;
  /// Receives each accepted goal, as for `rclcpp_action::create_server`.
  using AcceptedCallback = typename rclcpp_action::Server<ActionT>::AcceptedCallback;

  /// Create the action server.
  /**
   * \tparam NodeT Any node type accepted by `rclcpp_action::create_server`, such as `rclcpp::Node *`.
   * \param[in] node The node that owns the action server.
   * \param[in] name Name of the action.
   * \param[in] handle_goal Called for each goal sent while the server is active.
   * \param[in] handle_cancel Called for each cancel request.
   * \param[in] handle_accepted Called for each accepted goal, after the server records it.
   * \param[in] options Options of the underlying `rcl_action_server_t`.
   * \param[in] group Callback group of the server, or null for the default group.
   */
  template <typename NodeT>
  ActiveOnlyActionServer(
    NodeT node,
    const std::string & name,
    GoalCallback handle_goal,
    CancelCallback handle_cancel,
    AcceptedCallback handle_accepted,
    const rcl_action_server_options_t & options = rcl_action_server_get_default_options(),
    rclcpp::CallbackGroup::SharedPtr group = nullptr)
  {
    server_ = rclcpp_action::create_server<ActionT>(
      node,
      name,
      [this, handle_goal = std::move(handle_goal)](
        const rclcpp_action::GoalUUID & uuid, std::shared_ptr<const typename ActionT::Goal> goal) {
        if (!is_activated()) {
          return rclcpp_action::GoalResponse::REJECT;
        }
        return handle_goal(uuid, std::move(goal));
      },
      std::move(handle_cancel),
      [this, handle_accepted = std::move(handle_accepted)](std::shared_ptr<GoalHandle> goal_handle) {
        if (!record(goal_handle)) {
          end_goal(*goal_handle);
          return;
        }
        handle_accepted(std::move(goal_handle));
      },
      options,
      std::move(group));
  }

  ActiveOnlyActionServer(const ActiveOnlyActionServer &) = delete;
  ActiveOnlyActionServer & operator=(const ActiveOnlyActionServer &) = delete;

  /// Become inactive, then end every recorded goal that is still active.
  void on_deactivate() override
  {
    SimpleManagedEntity::on_deactivate();
    std::vector<std::weak_ptr<GoalHandle>> goals;
    {
      std::lock_guard<std::mutex> lock(mutex_);
      goals.swap(goals_);
    }
    for (const auto & weak_goal : goals) {
      if (auto goal_handle = weak_goal.lock()) {
        end_goal(*goal_handle);
      }
    }
  }

private:
  /// Remember a goal, and forget the ones that are gone.
  /// Returns false when the server deactivated meanwhile, so the caller ends the goal itself.
  bool record(const std::shared_ptr<GoalHandle> & goal_handle)
  {
    std::lock_guard<std::mutex> lock(mutex_);
    if (!is_activated()) {
      return false;
    }
    goals_.erase(
      std::remove_if(goals_.begin(), goals_.end(), [](const auto & goal) { return goal.expired(); }), goals_.end());
    goals_.push_back(goal_handle);
    return true;
  }

  /// End a goal, retrying once when a call throws but the goal is still active.
  /// A throw from a goal that went terminal concurrently is final, but a deferred goal that the author executed
  /// concurrently makes `execute()` throw while the goal still needs to be aborted.
  static void end_goal(GoalHandle & goal_handle)
  {
    for (int attempt = 0; attempt < 2; ++attempt) {
      if (try_end_goal(goal_handle)) {
        return;
      }
    }
  }

  /// Returns false when a call threw and the goal is still active, so the caller can try again.
  static bool try_end_goal(GoalHandle & goal_handle)
  {
    try {
      if (!goal_handle.is_active()) {
        return true;
      }
      auto result = std::make_shared<typename ActionT::Result>();
      if (goal_handle.is_canceling()) {
        goal_handle.canceled(std::move(result));
        return true;
      }
      if (!goal_handle.is_executing()) {
        goal_handle.execute();
      }
      goal_handle.abort(std::move(result));
      return true;
    } catch (const rclcpp::exceptions::RCLError &) {
      return !goal_handle.is_active();
    }
  }

  std::mutex mutex_;
  std::vector<std::weak_ptr<GoalHandle>> goals_;
  typename rclcpp_action::Server<ActionT>::SharedPtr server_;
};

}  // namespace nodl_runtime_cpp
