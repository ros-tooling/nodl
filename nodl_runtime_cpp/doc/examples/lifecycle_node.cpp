// SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
// SPDX-License-Identifier: Apache-2.0
#include "nodl_runtime_cpp/lifecycle_node.hpp"

#include <memory>
#include <thread>

#include "example_interfaces/action/fibonacci.hpp"
#include "example_interfaces/msg/int32.hpp"
#include "example_interfaces/srv/add_two_ints.hpp"
#include "nodl_runtime_cpp/active_only_action_server.hpp"
#include "nodl_runtime_cpp/active_only_client.hpp"
#include "nodl_runtime_cpp/active_only_service.hpp"
#include "nodl_runtime_cpp/active_only_subscription.hpp"
#include "rclcpp/rclcpp.hpp"
#include "rclcpp_action/rclcpp_action.hpp"
#include "std_msgs/msg/string.hpp"

/// Example of a non-generated node that uses `nodl_runtime_cpp::LifecycleNode`, and publishes a greeting when it activates.
/**
 * The endpoint is created by hand to keep the example self-contained, where a generated node creates its own.
 */
class Greeter : public nodl_runtime_cpp::LifecycleNode
{
public:
  Greeter()
  : nodl_runtime_cpp::LifecycleNode("greeter")
  , publisher_(create_publisher<std_msgs::msg::String>("greeting", 10))
  {}

protected:
  // Lifecycle publishers are already active here, so the hook never activates them.
  CallbackReturn handle_activate(const rclcpp_lifecycle::State & /*previous_state*/) override
  {
    std_msgs::msg::String greeting;
    greeting.data = "hello";
    publisher_->publish(greeting);
    return CallbackReturn::SUCCESS;
  }

  // Lifecycle publishers are deactivated after this hook returns SUCCESS.
  CallbackReturn handle_deactivate(const rclcpp_lifecycle::State & /*previous_state*/) override
  {
    RCLCPP_INFO(get_logger(), "goodbye");
    return CallbackReturn::SUCCESS;
  }

private:
  rclcpp_lifecycle::LifecyclePublisher<std_msgs::msg::String>::SharedPtr publisher_;
};

using AddTwoInts = example_interfaces::srv::AddTwoInts;
using Int32 = example_interfaces::msg::Int32;

/// Example of a non-generated node that puts a subscription, a service server and a client behind `nodl_runtime_cpp::LifecycleNode`'s gate.
/**
 * It doubles the numbers it receives, adds numbers on request and asks a peer to add numbers, and blocks all three while it is inactive.
 * The endpoints are created by hand to keep the example self-contained, where a generated node creates its own.
 */
class Doubler : public nodl_runtime_cpp::LifecycleNode
{
public:
  Doubler()
  : nodl_runtime_cpp::LifecycleNode("doubler")
  , publisher_(create_publisher<Int32>("doubled", 10))
  {
    // The gate is open from the standard activation until the standard deactivation.
    subscription_ = create_subscription<Int32>(
      "numbers",
      10,
      nodl_runtime_cpp::active_only_subscription_callback<Int32>(gate(), [this](std::shared_ptr<const Int32> message) {
        Int32 doubled;
        doubled.data = 2 * message->data;
        publisher_->publish(doubled);
      }));

    // A request that arrives while the gate is closed gets no response.
    service_ = nodl_runtime_cpp::create_active_only_service<AddTwoInts>(
      *this,
      gate(),
      "add",
      [](std::shared_ptr<AddTwoInts::Request> request, std::shared_ptr<AddTwoInts::Response> response) {
        response->sum = request->a + request->b;
      });

    // Sending throws nodl_runtime_cpp::InactiveError until the gate is open.
    client_ =
      std::make_shared<nodl_runtime_cpp::ActiveOnlyClient<AddTwoInts>>(gate(), create_client<AddTwoInts>("remote_add"));
  }

protected:
  // The gate is already open here, so the node can call a client.
  CallbackReturn handle_activate(const rclcpp_lifecycle::State & /*previous_state*/) override
  {
    auto request = std::make_shared<AddTwoInts::Request>();
    request->a = 1;
    request->b = 2;
    client_->async_send_request(request);
    return CallbackReturn::SUCCESS;
  }

private:
  rclcpp_lifecycle::LifecyclePublisher<Int32>::SharedPtr publisher_;
  rclcpp::Subscription<Int32>::SharedPtr subscription_;
  rclcpp::Service<AddTwoInts>::SharedPtr service_;
  nodl_runtime_cpp::ActiveOnlyClient<AddTwoInts>::SharedPtr client_;
};

using Fibonacci = example_interfaces::action::Fibonacci;
using FibonacciGoalHandle = rclcpp_action::ServerGoalHandle<Fibonacci>;

/// Example of a non-generated node that serves an action with `nodl_runtime_cpp::ActiveOnlyActionServer`, only while active.
/**
 * Goals end when the node deactivates.
 * The server is created by hand to keep the example self-contained, where a generated node creates its own.
 */
class Counter : public nodl_runtime_cpp::LifecycleNode
{
public:
  Counter()
  : nodl_runtime_cpp::LifecycleNode("counter")
  , server_(std::make_shared<nodl_runtime_cpp::ActiveOnlyActionServer<Fibonacci>>(
      this,
      "count",
      [](const rclcpp_action::GoalUUID &, std::shared_ptr<const Fibonacci::Goal>) {
        return rclcpp_action::GoalResponse::ACCEPT_AND_EXECUTE;
      },
      [](std::shared_ptr<FibonacciGoalHandle>) { return rclcpp_action::CancelResponse::ACCEPT; },
      [](std::shared_ptr<FibonacciGoalHandle> goal_handle) {
        // Do not block here. The node aborts the goal when it deactivates, so the worker checks is_active().
        std::thread([goal_handle] {
          for (int i = 0; i < goal_handle->get_goal()->order && goal_handle->is_active(); ++i) {
            std::this_thread::sleep_for(std::chrono::milliseconds(100));
          }
          try {
            goal_handle->succeed(std::make_shared<Fibonacci::Result>());
          } catch (const rclcpp::exceptions::RCLError &) {
            // The goal ended while the worker was finishing, so there is nothing left to report.
          }
        }).detach();
      }))
  {
    // Goals are rejected until the node activates, and active goals end when it deactivates.
    add_managed_entity(server_);
  }

private:
  nodl_runtime_cpp::ActiveOnlyActionServer<Fibonacci>::SharedPtr server_;
};

int main(int argc, char ** argv)
{
  rclcpp::init(argc, argv);
  auto node = std::make_shared<Greeter>();
  rclcpp::spin(node->get_node_base_interface());
  rclcpp::shutdown();
  return 0;
}
