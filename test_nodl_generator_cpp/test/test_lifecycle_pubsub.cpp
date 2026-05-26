#include <chrono>
#include <memory>
#include <string>

#include <gtest/gtest.h>
#include <rclcpp/rclcpp.hpp>
#include <rclcpp_lifecycle/lifecycle_node.hpp>
#include <lifecycle_msgs/msg/state.hpp>
#include <std_msgs/msg/string.hpp>

#include "lifecycle_pubsub_node_derived.hpp"

using namespace std::chrono_literals;

class LifecyclePubsub : public ::testing::Test
{
protected:
  void SetUp() override { rclcpp::init(0, nullptr); }
  void TearDown() override { rclcpp::shutdown(); }
};

TEST_F(LifecyclePubsub, DefaultsToUnconfigured)
{
  auto node = std::make_shared<LifecyclePubsubNode>();
  EXPECT_EQ(node->get_current_state().id(), lifecycle_msgs::msg::State::PRIMARY_STATE_UNCONFIGURED);
}

// Lifecycle-specific behavior: before activate, the generated subscription
// still fires (subs are not lifecycle-gated), but the generated lifecycle
// publisher silently drops outbound messages. This is the property that
// distinguishes a lifecycle-emitted base from the plain-node one.
TEST_F(LifecyclePubsub, PublisherSilentBeforeActivate)
{
  auto node = std::make_shared<LifecyclePubsubNode>();
  auto harness = std::make_shared<rclcpp::Node>("test_harness_lc_inactive");

  // No configure() / activate() — node stays UNCONFIGURED.

  auto qos = rclcpp::QoS(10).reliable();
  std::string received;
  auto sub = harness->create_subscription<std_msgs::msg::String>(
    "/lc_echo_out", qos,
    [&received](std_msgs::msg::String::ConstSharedPtr msg) { received = msg->data; });
  auto pub = harness->create_publisher<std_msgs::msg::String>("/lc_echo_in", qos);

  rclcpp::executors::SingleThreadedExecutor exec;
  exec.add_node(node->get_node_base_interface());
  exec.add_node(harness);

  const auto disco_deadline = std::chrono::steady_clock::now() + 2s;
  while (std::chrono::steady_clock::now() < disco_deadline &&
         pub->get_subscription_count() == 0)
  {
    exec.spin_some();
    std::this_thread::sleep_for(10ms);
  }
  ASSERT_GT(pub->get_subscription_count(), 0u) << "derived sub not discovered";

  std_msgs::msg::String msg;
  msg.data = "before-activate";
  pub->publish(msg);

  // Give the executor a generous window — sub callback should fire, but
  // the lifecycle publisher should drop the outbound echo.
  const auto deadline = std::chrono::steady_clock::now() + 500ms;
  while (std::chrono::steady_clock::now() < deadline) {
    exec.spin_some();
    std::this_thread::sleep_for(10ms);
  }

  EXPECT_EQ(node->receive_count, 1) << "subscription should fire regardless of state";
  EXPECT_EQ(node->last_received, "before-activate");
  EXPECT_TRUE(received.empty()) << "lifecycle publisher must not emit while inactive";
}

// Drive the state machine through configure → activate, then exercise the
// generated pub/sub end-to-end. Lifecycle publishers only emit when active,
// so a successful round-trip proves the activation propagated.
TEST_F(LifecyclePubsub, RoundTripWorksAfterActivate)
{
  auto node = std::make_shared<LifecyclePubsubNode>();
  auto harness = std::make_shared<rclcpp::Node>("test_harness_lc");

  ASSERT_EQ(node->configure().id(), lifecycle_msgs::msg::State::PRIMARY_STATE_INACTIVE);
  ASSERT_EQ(node->activate().id(), lifecycle_msgs::msg::State::PRIMARY_STATE_ACTIVE);

  auto qos = rclcpp::QoS(10).reliable();

  std::string received;
  auto sub = harness->create_subscription<std_msgs::msg::String>(
    "/lc_echo_out", qos,
    [&received](std_msgs::msg::String::ConstSharedPtr msg) { received = msg->data; });
  auto pub = harness->create_publisher<std_msgs::msg::String>("/lc_echo_in", qos);

  rclcpp::executors::SingleThreadedExecutor exec;
  exec.add_node(node->get_node_base_interface());
  exec.add_node(harness);

  const auto disco_deadline = std::chrono::steady_clock::now() + 2s;
  while (std::chrono::steady_clock::now() < disco_deadline &&
         (pub->get_subscription_count() == 0 || sub->get_publisher_count() == 0))
  {
    exec.spin_some();
    std::this_thread::sleep_for(10ms);
  }
  ASSERT_GT(pub->get_subscription_count(), 0u);
  ASSERT_GT(sub->get_publisher_count(), 0u);

  std_msgs::msg::String msg;
  msg.data = "world";
  pub->publish(msg);

  const auto recv_deadline = std::chrono::steady_clock::now() + 2s;
  while (std::chrono::steady_clock::now() < recv_deadline && received.empty()) {
    exec.spin_some();
    std::this_thread::sleep_for(10ms);
  }

  EXPECT_EQ(node->receive_count, 1);
  EXPECT_EQ(node->last_received, "world");
  EXPECT_EQ(received, "lc-echo: world");
}
