// SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
// SPDX-License-Identifier: Apache-2.0
#pragma once

#include <functional>
#include <memory>
#include <mutex>
#include <string>
#include <utility>

#include "nodl_runtime_cpp/gate.hpp"
#include "rclcpp/service.hpp"

namespace nodl_runtime_cpp
{

namespace detail
{

/// The service a deferred callback answers through, filled in once the service exists.
template <typename ServiceT>
class ServiceSlot
{
public:
  void set(const typename rclcpp::Service<ServiceT>::SharedPtr & service)
  {
    std::lock_guard<std::mutex> lock(mutex_);
    service_ = service;
  }

  typename rclcpp::Service<ServiceT>::SharedPtr get() const
  {
    std::lock_guard<std::mutex> lock(mutex_);
    return service_.lock();
  }

private:
  mutable std::mutex mutex_;
  std::weak_ptr<rclcpp::Service<ServiceT>> service_;
};

}  // namespace detail

/// Create a service server that answers requests only while the gate is open.
/**
 * A request that arrives while the gate is closed is dropped and no response is sent.
 * The server uses a deferred response, so the client's request never completes.
 *
 * \tparam ServiceT Service type.
 * \tparam NodeT Any node class with a `create_service` member, such as `rclcpp::Node`.
 * \param[in] node The node that owns the service.
 * \param[in] gate The activation gate, kept alive by the service callback.
 * \param[in] service_name Name of the service.
 * \param[in] callback Fills the response for each request received while the gate is open.
 * \param[in] args Remaining arguments of `create_service`, such as QoS and callback group.
 * \return The service, which the caller keeps alive.
 */
template <typename ServiceT, typename NodeT, typename... Args>
typename rclcpp::Service<ServiceT>::SharedPtr create_gated_service(
  NodeT & node,
  GatePtr gate,
  const std::string & service_name,
  std::function<void(std::shared_ptr<typename ServiceT::Request>, std::shared_ptr<typename ServiceT::Response>)>
    callback,
  Args &&... args)
{
  auto slot = std::make_shared<detail::ServiceSlot<ServiceT>>();
  auto deferred = [slot, gate = std::move(gate), callback = std::move(callback)](
                    std::shared_ptr<rmw_request_id_t> header, std::shared_ptr<typename ServiceT::Request> request) {
    if (!gate->is_activated()) {
      return;
    }
    auto service = slot->get();
    if (!service) {
      return;
    }
    auto response = std::make_shared<typename ServiceT::Response>();
    callback(std::move(request), response);
    service->send_response(*header, *response);
  };
  auto service = node.template create_service<ServiceT>(service_name, std::move(deferred), std::forward<Args>(args)...);
  slot->set(service);
  return service;
}

}  // namespace nodl_runtime_cpp
