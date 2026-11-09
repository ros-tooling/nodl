// SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
// SPDX-License-Identifier: Apache-2.0
#include <gtest/gtest.h>

#include <chrono>
#include <future>
#include <memory>
#include <stdexcept>
#include <thread>

#include "example_interfaces/action/fibonacci.hpp"
#include "example_interfaces/msg/int32.hpp"
#include "example_interfaces/srv/add_two_ints.hpp"
#include "nodl_runtime_cpp/gated_action_client.hpp"
#include "nodl_runtime_cpp/gated_client.hpp"
#include "nodl_runtime_cpp/active_only_service.hpp"
#include "nodl_runtime_cpp/active_only_subscription.hpp"
#include "nodl_runtime_cpp/lifecycle_node.hpp"
#include "rclcpp/rclcpp.hpp"
#include "rclcpp_action/rclcpp_action.hpp"

namespace
{

using AddTwoInts = example_interfaces::srv::AddTwoInts;
using Fibonacci = example_interfaces::action::Fibonacci;
using Int32 = example_interfaces::msg::Int32;
using std::chrono_literals::operator""ms;
using std::chrono_literals::operator""s;

/// A runtime lifecycle node that shows its gate to the test.
class ActiveOnlyNode : public nodl_runtime_cpp::LifecycleNode
{
public:
  ActiveOnlyNode()
  : nodl_runtime_cpp::LifecycleNode("active_only_node")
  {}

  using nodl_runtime_cpp::LifecycleNode::gate;
};

/// An active-only node, and a peer node that plays the other side of each entity.
/// One executor spins both on a background thread.
class ActiveOnlyEntities : public ::testing::Test
{
protected:
  static void SetUpTestSuite()
  {
    rclcpp::init(0, nullptr);
  }

  static void TearDownTestSuite()
  {
    rclcpp::shutdown();
  }

  void SetUp() override
  {
    node_ = std::make_shared<ActiveOnlyNode>();
    peer_ = std::make_shared<rclcpp::Node>("peer_node");
    gate_ = node_->gate();
    executor_.add_node(node_->get_node_base_interface());
    executor_.add_node(peer_);
    spinner_ = std::thread([this] { executor_.spin(); });
  }

  void TearDown() override
  {
    executor_.cancel();
    if (spinner_.joinable()) {
      spinner_.join();
    }
  }

  void open_gate()
  {
    node_->configure();
    node_->activate();
  }

  std::shared_ptr<ActiveOnlyNode> node_;
  std::shared_ptr<rclcpp::Node> peer_;
  nodl_runtime_cpp::GatePtr gate_;
  rclcpp::executors::SingleThreadedExecutor executor_;
  std::thread spinner_;
};

TEST_F(ActiveOnlyEntities, SubscriptionCallbackIsDroppedWhileClosed)
{
  std::promise<int> received;
  auto future = received.get_future();
  auto subscription = node_->create_subscription<Int32>(
    "chatter",
    10,
    nodl_runtime_cpp::active_only_subscription_callback<Int32>(
      gate_, [&received](std::shared_ptr<const Int32> message) { received.set_value(message->data); }));
  auto publisher = peer_->create_publisher<Int32>("chatter", 10);
  while (publisher->get_subscription_count() == 0) {
    std::this_thread::sleep_for(10ms);
  }

  Int32 message;
  message.data = 7;
  publisher->publish(message);
  EXPECT_EQ(future.wait_for(300ms), std::future_status::timeout);

  open_gate();
  publisher->publish(message);
  ASSERT_EQ(future.wait_for(5s), std::future_status::ready);
  EXPECT_EQ(future.get(), 7);
}

TEST_F(ActiveOnlyEntities, ServiceGetsNoResponseWhileClosed)
{
  auto service = nodl_runtime_cpp::create_active_only_service<AddTwoInts>(
    *node_,
    gate_,
    "add",
    [](std::shared_ptr<AddTwoInts::Request> request, std::shared_ptr<AddTwoInts::Response> response) {
      response->sum = request->a + request->b;
    });
  auto client = peer_->create_client<AddTwoInts>("add");
  ASSERT_TRUE(client->wait_for_service(5s));
  auto request = std::make_shared<AddTwoInts::Request>();
  request->a = 2;
  request->b = 3;

  auto dropped = client->async_send_request(request);
  EXPECT_EQ(dropped.future.wait_for(300ms), std::future_status::timeout);

  open_gate();
  auto answered = client->async_send_request(request);
  ASSERT_EQ(answered.future.wait_for(5s), std::future_status::ready);
  EXPECT_EQ(answered.future.get()->sum, 5);
}

TEST_F(ActiveOnlyEntities, ServiceStopsAnsweringAfterDeactivate)
{
  auto service = nodl_runtime_cpp::create_active_only_service<AddTwoInts>(
    *node_,
    gate_,
    "add",
    [](std::shared_ptr<AddTwoInts::Request> request, std::shared_ptr<AddTwoInts::Response> response) {
      response->sum = request->a + request->b;
    });
  auto client = peer_->create_client<AddTwoInts>("add");
  ASSERT_TRUE(client->wait_for_service(5s));
  auto request = std::make_shared<AddTwoInts::Request>();
  open_gate();
  node_->deactivate();

  auto dropped = client->async_send_request(request);

  EXPECT_EQ(dropped.future.wait_for(300ms), std::future_status::timeout);
}

TEST_F(ActiveOnlyEntities, ThrowingServiceCallbackLeavesRequestUnanswered)
{
  auto service = nodl_runtime_cpp::create_active_only_service<AddTwoInts>(
    *node_, gate_, "add", [](std::shared_ptr<AddTwoInts::Request>, std::shared_ptr<AddTwoInts::Response>) {
      throw std::runtime_error("callback failed");
    });
  auto client = peer_->create_client<AddTwoInts>("add");
  ASSERT_TRUE(client->wait_for_service(5s));
  open_gate();
  // The exception leaves the executor, so spin it from the test thread.
  executor_.cancel();
  spinner_.join();

  auto request = client->async_send_request(std::make_shared<AddTwoInts::Request>());
  bool threw = false;
  const auto deadline = std::chrono::steady_clock::now() + 5s;
  while (!threw && std::chrono::steady_clock::now() < deadline) {
    try {
      executor_.spin_some(10ms);
    } catch (const std::runtime_error &) {
      threw = true;
    }
  }

  EXPECT_TRUE(threw);
  EXPECT_EQ(request.future.wait_for(300ms), std::future_status::timeout);
}

TEST_F(GatedEntities, ServiceClientSendThrowsWhileClosed)
{
  auto service = peer_->create_service<AddTwoInts>(
    "add", [](std::shared_ptr<AddTwoInts::Request> request, std::shared_ptr<AddTwoInts::Response> response) {
      response->sum = request->a + request->b;
    });
  nodl_runtime_cpp::GatedClient<AddTwoInts> client(gate_, node_->create_client<AddTwoInts>("add"));
  ASSERT_TRUE(client.wait_for_service(5s));
  auto request = std::make_shared<AddTwoInts::Request>();
  request->a = 4;
  request->b = 5;

  EXPECT_THROW(client.async_send_request(request), nodl_runtime_cpp::InactiveError);

  open_gate();
  auto sent = client.async_send_request(request);
  ASSERT_EQ(sent.future.wait_for(5s), std::future_status::ready);
  EXPECT_EQ(sent.future.get()->sum, 9);
}

TEST_F(GatedEntities, WaitingForServiceIsNotGated)
{
  auto service = peer_->create_service<AddTwoInts>(
    "add", [](std::shared_ptr<AddTwoInts::Request>, std::shared_ptr<AddTwoInts::Response>) {});
  nodl_runtime_cpp::GatedClient<AddTwoInts> client(gate_, node_->create_client<AddTwoInts>("add"));

  EXPECT_TRUE(client.wait_for_service(5s));
  EXPECT_TRUE(client.service_is_ready());
}

TEST_F(GatedEntities, ClientsExposeTheWrappedClient)
{
  auto service_client = node_->create_client<AddTwoInts>("add");
  auto action_client = rclcpp_action::create_client<Fibonacci>(node_, "fibonacci");

  EXPECT_EQ(nodl_runtime_cpp::GatedClient<AddTwoInts>(gate_, service_client).client(), service_client);
  EXPECT_EQ(nodl_runtime_cpp::GatedActionClient<Fibonacci>(gate_, action_client).client(), action_client);
}

TEST_F(GatedEntities, ActionClientSendThrowsWhileClosed)
{
  auto server = rclcpp_action::create_server<Fibonacci>(
    peer_,
    "fibonacci",
    [](const rclcpp_action::GoalUUID &, std::shared_ptr<const Fibonacci::Goal>) {
      return rclcpp_action::GoalResponse::ACCEPT_AND_EXECUTE;
    },
    [](std::shared_ptr<rclcpp_action::ServerGoalHandle<Fibonacci>>) { return rclcpp_action::CancelResponse::ACCEPT; },
    [](std::shared_ptr<rclcpp_action::ServerGoalHandle<Fibonacci>> goal_handle) {
      goal_handle->succeed(std::make_shared<Fibonacci::Result>());
    });
  nodl_runtime_cpp::GatedActionClient<Fibonacci> client(
    gate_, rclcpp_action::create_client<Fibonacci>(node_, "fibonacci"));
  ASSERT_TRUE(client.wait_for_action_server(5s));
  EXPECT_TRUE(client.action_server_is_ready());
  Fibonacci::Goal goal;
  goal.order = 3;

  EXPECT_THROW(client.async_send_goal(goal), nodl_runtime_cpp::InactiveError);

  open_gate();
  auto goal_handle = client.async_send_goal(goal);
  ASSERT_EQ(goal_handle.wait_for(5s), std::future_status::ready);
  EXPECT_NE(goal_handle.get(), nullptr);
}

}  // namespace
