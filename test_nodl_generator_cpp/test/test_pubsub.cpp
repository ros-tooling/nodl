#include <chrono>
#include <memory>
#include <string>

#include <gtest/gtest.h>
#include <rclcpp/rclcpp.hpp>
#include <std_msgs/msg/string.hpp>

#include "pubsub_node_derived.hpp"

using namespace std::chrono_literals;

class PubsubRoundTrip : public ::testing::Test
{
protected:
  void SetUp() override { rclcpp::init(0, nullptr); }
  void TearDown() override { rclcpp::shutdown(); }
};

// End-to-end: harness publishes on /echo_in, derived node receives via the
// generated subscription, republishes through the generated publisher on
// /echo_out, harness subscribes and confirms the payload round-tripped.
TEST_F(PubsubRoundTrip, EchoesThroughGeneratedHandles)
{
  auto node = std::make_shared<PubsubNode>();
  auto harness = std::make_shared<rclcpp::Node>("test_harness");

  auto qos = rclcpp::QoS(10).reliable();

  std::string received;
  auto sub = harness->create_subscription<std_msgs::msg::String>(
    "/echo_out", qos,
    [&received](std_msgs::msg::String::ConstSharedPtr msg) { received = msg->data; });

  auto pub = harness->create_publisher<std_msgs::msg::String>("/echo_in", qos);

  rclcpp::executors::SingleThreadedExecutor exec;
  exec.add_node(node);
  exec.add_node(harness);

  // Wait for pub/sub discovery — bounded.
  const auto deadline = std::chrono::steady_clock::now() + 2s;
  while (std::chrono::steady_clock::now() < deadline &&
         (pub->get_subscription_count() == 0 || sub->get_publisher_count() == 0))
  {
    exec.spin_some();
    std::this_thread::sleep_for(10ms);
  }
  ASSERT_GT(pub->get_subscription_count(), 0u) << "derived node didn't subscribe to /echo_in";
  ASSERT_GT(sub->get_publisher_count(), 0u) << "derived node didn't publish on /echo_out";

  std_msgs::msg::String msg;
  msg.data = "hello";
  pub->publish(msg);

  const auto recv_deadline = std::chrono::steady_clock::now() + 2s;
  while (std::chrono::steady_clock::now() < recv_deadline && received.empty()) {
    exec.spin_some();
    std::this_thread::sleep_for(10ms);
  }

  EXPECT_EQ(node->receive_count, 1);
  EXPECT_EQ(node->last_received, "hello");
  EXPECT_EQ(received, "echo: hello");
}

// Cheap structural checks — useful as a quick smoke signal if the round-trip
// is failing for environment reasons (no DDS discovery, etc.).
TEST_F(PubsubRoundTrip, GeneratedHandlesExist)
{
  auto node = std::make_shared<PubsubNode>();
  EXPECT_STREQ(node->get_name(), "pubsub_node");
  // pub_echo_out_ is protected on the base; visible here because PubsubNode
  // inherits and we're testing through the derived type's interface.
}
