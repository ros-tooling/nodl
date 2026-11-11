// SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
// SPDX-License-Identifier: Apache-2.0
#pragma once

#include <algorithm>
#include <memory>
#include <mutex>
#include <utility>
#include <vector>

#include "rclcpp/exceptions.hpp"
#include "rclcpp_action/server.hpp"
#include "rclcpp_action/server_goal_handle.hpp"

namespace nodl_runtime_cpp
{

/// Records the goals an action server accepts, and ends the ones that are still active.
/**
 * `LifecycleNode::manage_action_server` owns one and passes it to the creator of the server.
 * Wrap the accepted callback of the server with `accepted`, and `end_all` ends each recorded goal that is still active
 * with a default-constructed result: `abort()` for executing and deferred goals, and `canceled()` for canceling goals.
 * A call that throws because the goal went terminal is skipped, and one that throws while the goal is still active
 * is retried once.
 *
 * \tparam ActionT Action type.
 */
template <typename ActionT>
class GoalTracker
{
public:
  /// Handle of an accepted goal.
  using GoalHandle = rclcpp_action::ServerGoalHandle<ActionT>;
  /// Receives each accepted goal, as for `rclcpp_action::create_server`.
  using AcceptedCallback = typename rclcpp_action::Server<ActionT>::AcceptedCallback;

  /// Starts recording goals.
  void open()
  {
    std::lock_guard<std::mutex> lock(mutex_);
    closed_ = false;
  }

  /// Returns an accepted callback that records the goal, then calls `accepted`.
  /**
   * A goal accepted after `end_all` is ended at once and `accepted` is not called.
   * The tracker must outlive the returned callback.
   */
  AcceptedCallback accepted(AcceptedCallback accepted)
  {
    return [this, accepted = std::move(accepted)](std::shared_ptr<GoalHandle> goal_handle) {
      if (!record(goal_handle)) {
        end_goal(*goal_handle);
        return;
      }
      accepted(std::move(goal_handle));
    };
  }

  /// Stops recording goals, and ends every recorded goal that is still active.
  void end_all()
  {
    std::vector<std::weak_ptr<GoalHandle>> goals;
    {
      std::lock_guard<std::mutex> lock(mutex_);
      closed_ = true;
      goals.swap(goals_);
    }
    for (const auto & weak_goal : goals) {
      if (auto goal_handle = weak_goal.lock()) {
        end_goal(*goal_handle);
      }
    }
  }

private:
  /// Remembers a goal, and forgets the ones that are gone.
  /// Returns false when the tracker is closed, so the caller ends the goal itself.
  bool record(const std::shared_ptr<GoalHandle> & goal_handle)
  {
    std::lock_guard<std::mutex> lock(mutex_);
    if (closed_) {
      return false;
    }
    goals_.erase(
      std::remove_if(goals_.begin(), goals_.end(), [](const auto & goal) { return goal.expired(); }), goals_.end());
    goals_.push_back(goal_handle);
    return true;
  }

  /// Ends a goal, retrying once when a call throws but the goal is still active.
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
  bool closed_ = true;
};

}  // namespace nodl_runtime_cpp
