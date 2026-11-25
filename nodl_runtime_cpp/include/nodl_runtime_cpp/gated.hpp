// SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
// SPDX-License-Identifier: Apache-2.0
#pragma once

#include <atomic>
#include <memory>
#include <utility>

#include "nodl_runtime_cpp/lifecycle_node.hpp"

namespace nodl_runtime_cpp
{

/// A member that holds an outgoing entity of a `LifecycleNode` and hands it out only while the node is active.
/**
 * The entity exists for the lifetime of the node, so a client keeps its graph presence and discovery.
 * `get()` returns it from the standard activation until the standard deactivation, and null otherwise.
 * The flag turns on before `handle_activate` and off after `handle_deactivate`,
 * so both hooks get the entity, and a failed activation turns it off again.
 *
 * `get()` is lock-free and safe to call from any thread.
 * A pointer obtained while the node is active stays usable after it deactivates, as a `LifecyclePublisher` pointer does.
 *
 * Declare it as a member of the node and construct it in the member initializer list.
 * `Gated` members register an activation slot in declaration order, with the `Managed` members.
 * Destroying a `Gated` unregisters its slot and is safe in any state.
 *
 * \tparam EntityT Type of the entity, such as `rclcpp::Client<ServiceT>`.
 */
template <typename EntityT>
class Gated
{
public:
  /// Registers the slot with `node`, which must outlive this object.
  /**
   * \throws std::logic_error When the node is activating or active.
   */
  Gated(LifecycleNode & node, std::shared_ptr<EntityT> entity)
  : node_(node)
  , entity_(std::move(entity))
  , slot_id_(node.add_activation_slot([this] { active_.store(true); }, [this] { active_.store(false); }))
  {}

  Gated(const Gated &) = delete;
  Gated(Gated &&) = delete;
  Gated & operator=(const Gated &) = delete;
  Gated & operator=(Gated &&) = delete;

  ~Gated()
  {
    node_.discard_activation_slot(slot_id_);
  }

  /// The entity while the node is active, otherwise null.
  std::shared_ptr<EntityT> get() const
  {
    return active_.load() ? entity_ : nullptr;
  }

private:
  LifecycleNode & node_;
  const std::shared_ptr<EntityT> entity_;
  std::atomic<bool> active_{false};
  const LifecycleNode::SlotId slot_id_;
};

}  // namespace nodl_runtime_cpp
