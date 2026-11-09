// SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
// SPDX-License-Identifier: Apache-2.0
#include <gtest/gtest.h>

#include <atomic>
#include <chrono>
#include <memory>
#include <type_traits>

#include "geometry_msgs/msg/twist.hpp"
#include "lifecycle_msgs/msg/state.hpp"
#include "rclcpp/rclcpp.hpp"
#include "std_srvs/srv/trigger.hpp"
#include "test_nodl_generators/cpp_lifecycle_node_base.hpp"

namespace
{

using std::chrono_literals::operator""ms;

/// Implements only what the generated base requires, publishes from `handle_activate`, and counts its callbacks.
class TestNode : public CppLifecycleNodeBase
{
  static_assert(
    std::is_same_v<decltype(pub_status_), rclcpp_lifecycle::LifecyclePublisher<std_msgs::msg::String>::SharedPtr>,
    "publisher_type selects the publisher class template");

  static_assert(
    std::is_base_of_v<nodl_runtime_cpp::LifecycleNode, CppLifecycleNodeBase>,
    "the lifecycle base class is the nodl runtime base");

public:
  /// Publishes one message, which is dropped while the publisher is inactive.
  void publish_status()
  {
    std_msgs::msg::String message;
    message.data = "status";
    pub_status_->publish(message);
  }

protected:
  CallbackReturn handle_activate(const rclcpp_lifecycle::State &) override
  {
    publish_status();
    return CallbackReturn::SUCCESS;
  }

  void on_cmd_vel(geometry_msgs::msg::Twist::ConstSharedPtr /*msg*/) override
  {
    ++cmd_vel_count;
  }

  void on_trigger(
    std_srvs::srv::Trigger::Request::SharedPtr, std_srvs::srv::Trigger::Response::SharedPtr response) override
  {
    response->success = true;
    response->message = "served";
  }

public:
  std::atomic<int> cmd_vel_count{0};
};

class GeneratedLifecycleNode : public ::testing::Test
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
    subscription_ = peer_->create_subscription<std_msgs::msg::String>(
      "status", 10, [this](std_msgs::msg::String::ConstSharedPtr) { ++received_; });
    executor_.add_node(node_->get_node_base_interface());
    executor_.add_node(peer_);
  }

  /// Spins both nodes until `count` messages arrived in total, or the timeout passes.
  void spin_until_received(int count, std::chrono::milliseconds timeout)
  {
    const auto deadline = std::chrono::steady_clock::now() + timeout;
    while (received_ < count && std::chrono::steady_clock::now() < deadline) {
      executor_.spin_some(10ms);
    }
  }

  /// Waits for the status publisher to match the subscription, so a later publication is not lost to discovery.
  void wait_for_match()
  {
    const auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(5);
    while (0 == subscription_->get_publisher_count() && std::chrono::steady_clock::now() < deadline) {
      executor_.spin_some(10ms);
    }
  }

  /// Waits until the command subscription and the service are matched with the peer.
  void wait_for_endpoints()
  {
    const auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(5);
    while ((0 == publisher_->get_subscription_count() || !client_->service_is_ready()) &&
           std::chrono::steady_clock::now() < deadline)
    {
      executor_.spin_some(10ms);
    }
  }

  /// Whether the subscription delivers a message published now.
  bool subscription_delivers()
  {
    const auto before = node_->cmd_vel_count.load();
    publisher_->publish(geometry_msgs::msg::Twist{});
    const auto deadline = std::chrono::steady_clock::now() + 500ms;
    while (node_->cmd_vel_count.load() == before && std::chrono::steady_clock::now() < deadline) {
      executor_.spin_some(10ms);
    }
    return node_->cmd_vel_count.load() > before;
  }

  /// Whether the service answers a request sent now.
  bool service_responds()
  {
    auto future = client_->async_send_request(std::make_shared<std_srvs::srv::Trigger::Request>());
    return rclcpp::FutureReturnCode::SUCCESS == executor_.spin_until_future_complete(future, 500ms);
  }

  std::shared_ptr<TestNode> node_ = std::make_shared<TestNode>();
  std::shared_ptr<rclcpp::Node> peer_ = std::make_shared<rclcpp::Node>("peer_node");
  rclcpp::Subscription<std_msgs::msg::String>::SharedPtr subscription_;
  rclcpp::Publisher<geometry_msgs::msg::Twist>::SharedPtr publisher_ =
    peer_->create_publisher<geometry_msgs::msg::Twist>("cmd_vel", rclcpp::QoS(1).best_effort());
  rclcpp::Client<std_srvs::srv::Trigger>::SharedPtr client_ = peer_->create_client<std_srvs::srv::Trigger>("trigger");
  rclcpp::executors::SingleThreadedExecutor executor_;
  int received_ = 0;
};

TEST_F(GeneratedLifecycleNode, PublishesOnlyWhileActive)
{
  EXPECT_EQ(node_->configure().id(), lifecycle_msgs::msg::State::PRIMARY_STATE_INACTIVE);
  wait_for_match();
  node_->publish_status();
  spin_until_received(1, 300ms);
  EXPECT_EQ(received_, 0);

  // handle_activate publishes while the publisher is already active.
  EXPECT_EQ(node_->activate().id(), lifecycle_msgs::msg::State::PRIMARY_STATE_ACTIVE);
  spin_until_received(1, std::chrono::seconds(5));
  EXPECT_EQ(received_, 1);

  node_->publish_status();
  spin_until_received(2, std::chrono::seconds(5));
  EXPECT_EQ(received_, 2);

  EXPECT_EQ(node_->deactivate().id(), lifecycle_msgs::msg::State::PRIMARY_STATE_INACTIVE);
  node_->publish_status();
  spin_until_received(3, 300ms);
  EXPECT_EQ(received_, 2);
}

TEST_F(GeneratedLifecycleNode, DeliversSubscriptionsAndServesRequestsOnlyWhileActive)
{
  wait_for_endpoints();

  // Unconfigured
  EXPECT_FALSE(subscription_delivers());
  EXPECT_FALSE(service_responds());

  // Inactive
  node_->configure();
  EXPECT_FALSE(subscription_delivers());
  EXPECT_FALSE(service_responds());

  // Active
  node_->activate();
  EXPECT_TRUE(subscription_delivers());
  EXPECT_TRUE(service_responds());

  // Inactive again
  node_->deactivate();
  EXPECT_FALSE(subscription_delivers());
  EXPECT_FALSE(service_responds());
}

}  // namespace
