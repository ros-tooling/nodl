// SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
// SPDX-License-Identifier: Apache-2.0
#pragma once

#include <chrono>
#include <memory>
#include <string>
#include <utility>

#include "nodl_runtime_cpp/gate.hpp"
#include "rclcpp/client.hpp"

namespace nodl_runtime_cpp
{

/// A service client whose `async_send_request` throws `InactiveError` while the gate is closed.
/**
 * The other methods forward to the wrapped client, and `client()` returns it.
 * See the `nodl_runtime_cpp` overview for what stays available while the gate is closed.
 *
 * \tparam ServiceT Service type.
 */
template <typename ServiceT>
class ActiveOnlyClient
{
public:
  /// Shared pointer to the wrapper, the type of a generated client member.
  using SharedPtr = std::shared_ptr<ActiveOnlyClient>;

  /// \param[in] gate The activation gate, shared with the node.
  /// \param[in] client The client to guard, usually from `create_client`.
  ActiveOnlyClient(GatePtr gate, typename rclcpp::Client<ServiceT>::SharedPtr client)
  : gate_(std::move(gate))
  , client_(std::move(client))
  {}

  /// Send a request, as `rclcpp::Client::async_send_request`.
  /**
   * \param[in] request The request to send.
   * \param[in] args Remaining arguments of `async_send_request`, such as a response callback.
   * \return What `async_send_request` returns.
   * \throws InactiveError if the gate is closed.
   */
  template <typename... Args>
  auto async_send_request(typename rclcpp::Client<ServiceT>::SharedRequest request, Args &&... args)
  {
    throw_if_closed(*gate_, std::string("Request to ") + client_->get_service_name());
    return client_->async_send_request(std::move(request), std::forward<Args>(args)...);
  }

  /// Wait for the service to become available, as `rclcpp::ClientBase::wait_for_service`.
  /// Always allowed.
  template <typename RepT = int64_t, typename RatioT = std::milli>
  bool wait_for_service(std::chrono::duration<RepT, RatioT> timeout = std::chrono::duration<RepT, RatioT>(-1))
  {
    return client_->wait_for_service(timeout);
  }

  /// Whether the service is available. Always allowed.
  bool service_is_ready() const
  {
    return client_->service_is_ready();
  }

  /// The guarded client, for calls that are always allowed.
  const typename rclcpp::Client<ServiceT>::SharedPtr & client() const
  {
    return client_;
  }

private:
  GatePtr gate_;
  typename rclcpp::Client<ServiceT>::SharedPtr client_;
};

}  // namespace nodl_runtime_cpp
