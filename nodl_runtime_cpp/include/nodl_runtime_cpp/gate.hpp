// SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
// SPDX-License-Identifier: Apache-2.0
#pragma once

#include <memory>
#include <stdexcept>
#include <string>

#include "rclcpp_lifecycle/managed_entity.hpp"

namespace nodl_runtime_cpp
{

/// The activation gate: open while the node is active, closed otherwise.
/**
 * A node owns one gate and registers it with `add_managed_entity`,
 * so the standard lifecycle activation opens and closes it.
 */
using Gate = rclcpp_lifecycle::SimpleManagedEntity;

/// Read-only shared handle to a gate, held by every active-only entity.
using GatePtr = std::shared_ptr<const Gate>;

/// Thrown by an active-only client when a request is sent while the gate is closed.
class InactiveError : public std::runtime_error
{
public:
  /// \param[in] what Description of the blocked operation.
  explicit InactiveError(const std::string & what)
  : std::runtime_error(what)
  {}
};

/// Throw `InactiveError` naming `operation` when the gate is closed.
/**
 * \param[in] gate The activation gate.
 * \param[in] operation What was attempted, for the error message.
 * \throws InactiveError if the gate is closed.
 */
inline void throw_if_closed(const Gate & gate, const std::string & operation)
{
  if (!gate.is_activated()) {
    throw InactiveError(operation + " blocked: the node is not active");
  }
}

}  // namespace nodl_runtime_cpp
