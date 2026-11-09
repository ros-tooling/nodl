// SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
// SPDX-License-Identifier: Apache-2.0
#include <gtest/gtest.h>

#include <atomic>
#include <chrono>
#include <memory>
#include <mutex>
#include <thread>
#include <utility>
#include <vector>

#include "example_interfaces/action/fibonacci.hpp"
#include "nodl_runtime_cpp/gated_action_server.hpp"
#include "rclcpp/rclcpp.hpp"
#include "rclcpp_action/rclcpp_action.hpp"
#include "rclcpp_lifecycle/lifecycle_node.hpp"

namespace
{

using Fibonacci = example_interfaces::action::Fibonacci;
using GoalHandle = rclcpp_action::ServerGoalHandle<Fibonacci>;
using ClientGoalHandle = rclcpp_action::ClientGoalHandle<Fibonacci>;
using std::chrono_literals::operator""ms;
using std::chrono_literals::operator""s;

/// An order that the goal callback of the fixture defers instead of executing.
constexpr int32_t kDefer = 1;

/// A plain lifecycle node that makes `add_managed_entity` public.
class PlainNode : public rclcpp_lifecycle::LifecycleNode
{
public:
  PlainNode()
  : rclcpp_lifecycle::LifecycleNode("gated_action_node")
  {}

  using rclcpp_lifecycle::LifecycleNode::add_managed_entity;
};

/// A gated action server on a plain lifecycle node, and a client on a peer node.
/// The server records each goal handle it is given and never works on it, so the test decides how goals end.
/// One executor spins both nodes on a background thread.
class GatedActionServerTest : public ::testing::Test
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
    node_ = std::make_shared<PlainNode>();
    peer_ = std::make_shared<rclcpp::Node>("peer_node");
    server_ = std::make_shared<nodl_runtime_cpp::GatedActionServer<Fibonacci>>(
      node_,
      "fibonacci",
      [](const rclcpp_action::GoalUUID &, std::shared_ptr<const Fibonacci::Goal> goal) {
        return kDefer == goal->order ? rclcpp_action::GoalResponse::ACCEPT_AND_DEFER
                                     : rclcpp_action::GoalResponse::ACCEPT_AND_EXECUTE;
      },
      [](std::shared_ptr<GoalHandle>) { return rclcpp_action::CancelResponse::ACCEPT; },
      [this](std::shared_ptr<GoalHandle> goal_handle) {
        std::lock_guard<std::mutex> lock(mutex_);
        handles_.push_back(std::move(goal_handle));
      });
    node_->add_managed_entity(server_);
    client_ = rclcpp_action::create_client<Fibonacci>(peer_, "fibonacci");
    executor_.add_node(node_->get_node_base_interface());
    executor_.add_node(peer_);
    spinner_ = std::thread([this] { executor_.spin(); });
    ASSERT_TRUE(client_->wait_for_action_server(5s));
  }

  void TearDown() override
  {
    executor_.cancel();
    if (spinner_.joinable()) {
      spinner_.join();
    }
  }

  void activate()
  {
    node_->configure();
    node_->activate();
  }

  /// A goal sent by the client, and the handle the server holds for it.
  struct Sent
  {
    std::shared_ptr<ClientGoalHandle> client;
    std::shared_future<ClientGoalHandle::WrappedResult> result;
    std::shared_ptr<GoalHandle> server;
  };

  /// Send a goal and wait until the server hands it out, or return an empty `Sent` when it is rejected.
  Sent send(int32_t order)
  {
    Sent sent;
    Fibonacci::Goal goal;
    goal.order = order;
    auto handle_future = client_->async_send_goal(goal);
    if (handle_future.wait_for(5s) != std::future_status::ready) {
      return sent;
    }
    sent.client = handle_future.get();
    if (!sent.client) {
      return sent;
    }
    sent.result = client_->async_get_result(sent.client);
    const auto deadline = std::chrono::steady_clock::now() + 5s;
    while (std::chrono::steady_clock::now() < deadline) {
      {
        std::lock_guard<std::mutex> lock(mutex_);
        if (handles_.size() > handles_seen_) {
          sent.server = handles_[handles_seen_++];
          return sent;
        }
      }
      std::this_thread::sleep_for(5ms);
    }
    return sent;
  }

  /// The final status of a goal, or -1 when it has no result in time.
  static int8_t status_of(const Sent & sent)
  {
    if (sent.result.wait_for(5s) != std::future_status::ready) {
      return -1;
    }
    return static_cast<int8_t>(sent.result.get().code);
  }

  std::shared_ptr<PlainNode> node_;
  std::shared_ptr<rclcpp::Node> peer_;
  std::shared_ptr<nodl_runtime_cpp::GatedActionServer<Fibonacci>> server_;
  rclcpp_action::Client<Fibonacci>::SharedPtr client_;
  rclcpp::executors::SingleThreadedExecutor executor_;
  std::thread spinner_;
  std::mutex mutex_;
  std::vector<std::shared_ptr<GoalHandle>> handles_;
  size_t handles_seen_ = 0;
};

constexpr int8_t kSucceeded = static_cast<int8_t>(rclcpp_action::ResultCode::SUCCEEDED);
constexpr int8_t kAborted = static_cast<int8_t>(rclcpp_action::ResultCode::ABORTED);
constexpr int8_t kCanceled = static_cast<int8_t>(rclcpp_action::ResultCode::CANCELED);

TEST_F(GatedActionServerTest, RejectsGoalsWhileInactiveAndAcceptsThemWhileActive)
{
  EXPECT_EQ(send(0).server, nullptr);

  activate();
  EXPECT_NE(send(0).server, nullptr);
}

TEST_F(GatedActionServerTest, AbortsAnExecutingGoalOnDeactivate)
{
  activate();
  auto sent = send(0);
  ASSERT_NE(sent.server, nullptr);
  ASSERT_TRUE(sent.server->is_executing());

  node_->deactivate();

  EXPECT_EQ(status_of(sent), kAborted);
}

TEST_F(GatedActionServerTest, AbortsADeferredGoalOnDeactivate)
{
  activate();
  auto sent = send(kDefer);
  ASSERT_NE(sent.server, nullptr);
  ASSERT_FALSE(sent.server->is_executing());

  node_->deactivate();

  EXPECT_EQ(status_of(sent), kAborted);
}

TEST_F(GatedActionServerTest, CancelsACancelingGoalOnDeactivate)
{
  activate();
  auto sent = send(0);
  ASSERT_NE(sent.server, nullptr);
  client_->async_cancel_goal(sent.client);
  const auto deadline = std::chrono::steady_clock::now() + 5s;
  while (!sent.server->is_canceling() && std::chrono::steady_clock::now() < deadline) {
    std::this_thread::sleep_for(5ms);
  }
  ASSERT_TRUE(sent.server->is_canceling());

  node_->deactivate();

  EXPECT_EQ(status_of(sent), kCanceled);
}

TEST_F(GatedActionServerTest, LeavesAGoalThatSucceededBeforeDeactivation)
{
  activate();
  auto sent = send(0);
  ASSERT_NE(sent.server, nullptr);
  sent.server->succeed(std::make_shared<Fibonacci::Result>());

  node_->deactivate();

  EXPECT_EQ(status_of(sent), kSucceeded);
}

TEST_F(GatedActionServerTest, ConcurrentSuccessDoesNotFailTheDeactivation)
{
  for (int i = 0; i < 20; ++i) {
    activate();
    auto sent = send(0);
    ASSERT_NE(sent.server, nullptr);
    std::atomic<bool> go{false};
    std::thread worker([&] {
      while (!go) {
      }
      try {
        sent.server->succeed(std::make_shared<Fibonacci::Result>());
      } catch (const rclcpp::exceptions::RCLError &) {
        // The deactivation aborted the goal first.
      }
    });
    go = true;

    EXPECT_NO_THROW(node_->deactivate());

    worker.join();
    const auto status = status_of(sent);
    EXPECT_TRUE(kSucceeded == status || kAborted == status) << "status " << static_cast<int>(status);
    node_->cleanup();
  }
}

TEST_F(GatedActionServerTest, AcceptsGoalsAgainAfterReactivation)
{
  activate();
  node_->deactivate();
  EXPECT_EQ(send(0).server, nullptr);

  node_->activate();
  EXPECT_NE(send(0).server, nullptr);
}

}  // namespace
