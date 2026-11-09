// SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
// SPDX-License-Identifier: Apache-2.0
#pragma once

#include <chrono>
#include <memory>
#include <utility>

#include "nodl_runtime_cpp/gate.hpp"
#include "rclcpp_action/client.hpp"

namespace nodl_runtime_cpp
{

/// An action client whose `async_send_goal` throws `InactiveError` while the gate is closed.
/**
 * The other methods forward to the wrapped client, and `client()` returns it.
 * See the `nodl_runtime_cpp` overview for what stays available while the gate is closed.
 *
 * \tparam ActionT Action type.
 */
template <typename ActionT>
class ActiveOnlyActionClient
{
public:
  /// Shared pointer to the wrapper, the type of a generated client member.
  using SharedPtr = std::shared_ptr<ActiveOnlyActionClient>;

  /// \param[in] gate The activation gate, shared with the node.
  /// \param[in] client The client to guard, usually from `rclcpp_action::create_client`.
  ActiveOnlyActionClient(GatePtr gate, typename rclcpp_action::Client<ActionT>::SharedPtr client)
  : gate_(std::move(gate))
  , client_(std::move(client))
  {}

  /// Send a goal, as `rclcpp_action::Client::async_send_goal`.
  /**
   * \param[in] goal The goal to send.
   * \param[in] options Goal, feedback and result callbacks.
   * \return What `async_send_goal` returns.
   * \throws InactiveError if the gate is closed.
   */
  auto async_send_goal(
    const typename ActionT::Goal & goal,
    const typename rclcpp_action::Client<ActionT>::SendGoalOptions & options =
      typename rclcpp_action::Client<ActionT>::SendGoalOptions())
  {
    throw_if_closed(*gate_, "Sending a goal");
    return client_->async_send_goal(goal, options);
  }

  /// Wait for the action server, as `rclcpp_action::ClientBase::wait_for_action_server`.
  /// Always allowed.
  template <typename RepT = int64_t, typename RatioT = std::milli>
  bool wait_for_action_server(std::chrono::duration<RepT, RatioT> timeout = std::chrono::duration<RepT, RatioT>(-1))
  {
    return client_->wait_for_action_server(timeout);
  }

  /// Whether the action server is available. Always allowed.
  bool action_server_is_ready() const
  {
    return client_->action_server_is_ready();
  }

  /// The guarded client, for cancel and result requests that are always allowed.
  const typename rclcpp_action::Client<ActionT>::SharedPtr & client() const
  {
    return client_;
  }

private:
  GatePtr gate_;
  typename rclcpp_action::Client<ActionT>::SharedPtr client_;
};

}  // namespace nodl_runtime_cpp
