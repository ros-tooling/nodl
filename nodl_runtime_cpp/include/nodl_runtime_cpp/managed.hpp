// SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
// SPDX-License-Identifier: Apache-2.0
#pragma once

#include <memory>
#include <utility>

#include "nodl_runtime_cpp/lifecycle_node.hpp"
#include "rclcpp/logging.hpp"

namespace nodl_runtime_cpp
{

/// A member that holds an endpoint of a `LifecycleNode` while the node is active.
/**
 * Declare it as a member of the node and construct it in the member initializer list.
 * It registers an activation slot with the node: `make` runs when the node activates, and the endpoint is destroyed when it deactivates.
 * `Managed` members register in declaration order, so reordering them changes the order of creation.
 *
 * Destroy it only while the node is not active, which unregisters the slot.
 * Destroying it while the node is activating or active and owned by a `std::shared_ptr` that is not being released is an error:
 * it is logged, and the endpoint and the slot are removed.
 * A node that is destroyed while active destroys its members, and that is not an error.
 * The error is detected only for a node owned by a `std::shared_ptr`, as a node created with `std::make_shared` or by a component container is.
 * A node on the stack is always treated as being destroyed: no error is logged and the executors are not woken.
 *
 * Create and destroy `Managed` objects from the thread that requests the transitions.
 *
 * Not to be confused with `rclcpp_lifecycle::ManagedEntityInterface`, which `rclcpp_lifecycle` uses to activate its own entities.
 *
 * \tparam EntityT Type of the endpoint, such as `rclcpp::Subscription<MessageT>`.
 */
template <typename EntityT>
class Managed
{
public:
  /// Registers the slot with `node`, which must outlive this object.
  /**
   * \tparam MakeT Callable that returns the endpoint as a `std::shared_ptr<EntityT>`.
   * \throws std::logic_error When the node is activating or active.
   */
  template <typename MakeT>
  Managed(LifecycleNode & node, MakeT make)
  : node_(node)
  , slot_id_(
      node.add_activation_slot([this, make = std::move(make)] { entity_ = make(); }, [this] { entity_.reset(); }))
  {}

  Managed(const Managed &) = delete;
  Managed(Managed &&) = delete;
  Managed & operator=(const Managed &) = delete;
  Managed & operator=(Managed &&) = delete;

  ~Managed()
  {
    const bool misused = node_.slots_locked_ && !node_.weak_from_this().expired();
    if (misused) {
      RCLCPP_ERROR(
        node_.get_logger(),
        "A Managed member was destroyed while its node is activating or active, "
        "create dynamic Managed members only while the node is not active and destroy them before it activates");
    }
    entity_.reset();
    node_.discard_activation_slot(slot_id_);
    if (misused) {
      node_.wake_executors();
    }
  }

  /// Whether the endpoint currently exists.
  explicit operator bool() const
  {
    return nullptr != entity_;
  }

private:
  LifecycleNode & node_;
  const LifecycleNode::SlotId slot_id_;
  std::shared_ptr<EntityT> entity_;
};

}  // namespace nodl_runtime_cpp
