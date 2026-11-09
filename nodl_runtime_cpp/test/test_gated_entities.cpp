// SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
// SPDX-License-Identifier: Apache-2.0
#include <gtest/gtest.h>

#include <chrono>
#include <future>
#include <memory>
#include <stdexcept>
#include <thread>

#include "example_interfaces/msg/int32.hpp"
#include "example_interfaces/srv/add_two_ints.hpp"
#include "nodl_runtime_cpp/gated_service.hpp"
#include "nodl_runtime_cpp/gated_subscription.hpp"
#include "nodl_runtime_cpp/lifecycle_node.hpp"
#include "rclcpp/rclcpp.hpp"

namespace
{

using AddTwoInts = example_interfaces::srv::AddTwoInts;
using Int32 = example_interfaces::msg::Int32;
using std::chrono_literals::operator""ms;
using std::chrono_literals::operator""s;

/// A runtime lifecycle node that shows its gate to the test.
class GatedNode : public nodl_runtime_cpp::LifecycleNode
{
public:
  GatedNode()
  : nodl_runtime_cpp::LifecycleNode("gated_node")
  {}

  using nodl_runtime_cpp::LifecycleNode::gate;
};

/// A gated node, and a peer node that plays the other side of each entity.
/// One executor spins both on a background thread.
class GatedEntities : public ::testing::Test
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
    node_ = std::make_shared<GatedNode>();
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

  std::shared_ptr<GatedNode> node_;
  std::shared_ptr<rclcpp::Node> peer_;
  nodl_runtime_cpp::GatePtr gate_;
  rclcpp::executors::SingleThreadedExecutor executor_;
  std::thread spinner_;
};

TEST_F(GatedEntities, SubscriptionCallbackIsDroppedWhileClosed)
{
  std::promise<int> received;
  auto future = received.get_future();
  auto subscription = node_->create_subscription<Int32>(
    "chatter",
    10,
    nodl_runtime_cpp::gate_subscription_callback<Int32>(
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

TEST_F(GatedEntities, ServiceGetsNoResponseWhileClosed)
{
  auto service = nodl_runtime_cpp::create_gated_service<AddTwoInts>(
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

TEST_F(GatedEntities, ServiceStopsAnsweringAfterDeactivate)
{
  auto service = nodl_runtime_cpp::create_gated_service<AddTwoInts>(
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

TEST_F(GatedEntities, ThrowingServiceCallbackLeavesRequestUnanswered)
{
  auto service = nodl_runtime_cpp::create_gated_service<AddTwoInts>(
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

}  // namespace
