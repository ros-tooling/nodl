// SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
// SPDX-License-Identifier: Apache-2.0
#include <gtest/gtest.h>

#include <chrono>
#include <memory>
#include <type_traits>

#include "lifecycle_msgs/msg/state.hpp"
#include "rclcpp/rclcpp.hpp"
#include "test_nodl_generators/cpp_lifecycle_node_base.hpp"

namespace
{

using std::chrono_literals::operator""ms;

/// Implements only what the generated base requires, and publishes from `handle_activate`.
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
  {}
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

  std::shared_ptr<TestNode> node_ = std::make_shared<TestNode>();
  std::shared_ptr<rclcpp::Node> peer_ = std::make_shared<rclcpp::Node>("peer_node");
  rclcpp::Subscription<std_msgs::msg::String>::SharedPtr subscription_;
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

}  // namespace
