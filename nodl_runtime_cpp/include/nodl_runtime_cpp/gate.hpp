// SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
// SPDX-License-Identifier: Apache-2.0
#pragma once

#include <memory>

#include "rclcpp_lifecycle/managed_entity.hpp"

namespace nodl_runtime_cpp
{

/// The activation gate: open while the node is active, closed otherwise.
/**
 * A node owns one gate and registers it with `add_managed_entity`,
 * so the standard lifecycle activation opens and closes it.
 */
using Gate = rclcpp_lifecycle::SimpleManagedEntity;

/// Read-only shared handle to a gate, held by every gated entity.
using GatePtr = std::shared_ptr<const Gate>;

}  // namespace nodl_runtime_cpp
