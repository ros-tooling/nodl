// SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
// SPDX-License-Identifier: Apache-2.0
#pragma once

#include <functional>
#include <memory>
#include <utility>

#include "nodl_runtime_cpp/gate.hpp"

namespace nodl_runtime_cpp
{

/// Wrap a subscription callback so it drops messages while the gate is closed.
/**
 * Messages that arrive while the gate is closed are dropped and the callback is not called.
 * Pass the result to `create_subscription` in place of the callback.
 *
 * \tparam MessageT Message type of the subscription.
 * \param[in] gate The activation gate, kept alive by the returned callback.
 * \param[in] callback Called with each message received while the gate is open.
 * \return A callback of the `std::shared_ptr<const MessageT>` form.
 */
template <typename MessageT>
std::function<void(std::shared_ptr<const MessageT>)> active_only_subscription_callback(
  GatePtr gate, std::function<void(std::shared_ptr<const MessageT>)> callback)
{
  return [gate = std::move(gate), callback = std::move(callback)](std::shared_ptr<const MessageT> message) {
    if (gate->is_activated()) {
      callback(std::move(message));
    }
  };
}

}  // namespace nodl_runtime_cpp
