// SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
// SPDX-License-Identifier: Apache-2.0
#include <gtest/gtest.h>

#include <algorithm>
#include <atomic>
#include <chrono>
#include <functional>
#include <memory>
#include <string>
#include <thread>
#include <type_traits>
#include <vector>

#include "lifecycle_msgs/msg/state.hpp"
#include "rclcpp/rclcpp.hpp"
#include "test_nodl_generators/cpp_lifecycle_node_base.hpp"

namespace
{

using std::chrono_literals::operator""ms;
using lifecycle_msgs::msg::State;

const std::chrono::seconds TIMEOUT(10);
const char NODE_NAME[] = "cpp_lifecycle_node";

/// Implements only what the generated base requires, and records what the endpoints do.
class TestNode : public CppLifecycleNodeBase
{
  static_assert(
    std::is_same_v<decltype(pub_status_), rclcpp::Publisher<std_msgs::msg::String>::SharedPtr>,
    "generated lifecycle publishers are plain publishers");

  static_assert(
    std::is_base_of_v<nodl_runtime_cpp::LifecycleNode, CppLifecycleNodeBase>,
    "the lifecycle base class is the nodl runtime base class");

public:
  /// Publishes one message on the status publisher, which must exist.
  void publish_status()
  {
    std_msgs::msg::String message;
    message.data = "status";
    pub_status_->publish(message);
  }

  /// Whether the generated publishers existed when each hook ran.
  std::atomic<bool> publishers_set_in_activate{false};
  std::atomic<bool> publishers_set_in_deactivate{false};
  std::atomic<int> cmd_vel_received{0};
  std::atomic<int> latched_received{0};
  /// The node's state when the latched sample was executed.
  std::atomic<int> state_of_latched_sample{-1};

protected:
  CallbackReturn handle_activate(const rclcpp_lifecycle::State &) override
  {
    publishers_set_in_activate = (nullptr != pub_status_) && (nullptr != pub_latched_status_);
    std_msgs::msg::String message;
    message.data = "initial";
    pub_latched_status_->publish(message);
    return CallbackReturn::SUCCESS;
  }

  CallbackReturn handle_deactivate(const rclcpp_lifecycle::State &) override
  {
    publishers_set_in_deactivate = (nullptr != pub_status_);
    return CallbackReturn::SUCCESS;
  }

  void on_cmd_vel(geometry_msgs::msg::Twist::ConstSharedPtr /*msg*/) override
  {
    ++cmd_vel_received;
  }

  void on_latched(std_msgs::msg::String::ConstSharedPtr /*msg*/) override
  {
    state_of_latched_sample = get_current_state().id();
    ++latched_received;
  }
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
    executor_.add_node(node_->get_node_base_interface());
    executor_.add_node(peer_);
  }

  /// Spins both nodes until the condition holds or the timeout passes, and returns whether it holds.
  bool spin_until(const std::function<bool()> & condition, std::chrono::milliseconds timeout = TIMEOUT)
  {
    const auto deadline = std::chrono::steady_clock::now() + timeout;
    while (!condition() && std::chrono::steady_clock::now() < deadline) {
      executor_.spin_some(10ms);
    }
    return condition();
  }

  /// Spins both nodes for a fixed time, to let something that should not happen happen.
  void spin_for(std::chrono::milliseconds duration)
  {
    spin_until([] { return false; }, duration);
  }

  static bool has_endpoint_of_node(const std::vector<rclcpp::TopicEndpointInfo> & endpoints)
  {
    return std::any_of(
      endpoints.begin(), endpoints.end(), [](const auto & endpoint) { return NODE_NAME == endpoint.node_name(); });
  }

  bool graph_has_publisher(const std::string & topic)
  {
    return has_endpoint_of_node(peer_->get_publishers_info_by_topic(topic));
  }

  bool graph_has_subscription(const std::string & topic)
  {
    return has_endpoint_of_node(peer_->get_subscriptions_info_by_topic(topic));
  }

  /// Waits until the node's built-in endpoints are visible, so an absent endpoint is not just undiscovered.
  void wait_for_node_discovery()
  {
    ASSERT_TRUE(spin_until([this] { return graph_has_publisher("/cpp_lifecycle_node/transition_event"); }));
  }

  /// Returns a latched subscriber on a topic of the node, created after the node published.
  std::shared_ptr<std::string> subscribe_latched_status()
  {
    auto received = std::make_shared<std::string>();
    late_subscriptions_.push_back(peer_->create_subscription<std_msgs::msg::String>(
      "latched_status",
      rclcpp::QoS(1).reliable().transient_local(),
      [received](std_msgs::msg::String::ConstSharedPtr msg) { *received = msg->data; }));
    return received;
  }

  std::shared_ptr<TestNode> node_ = std::make_shared<TestNode>();
  std::shared_ptr<rclcpp::Node> peer_ = std::make_shared<rclcpp::Node>("peer_node");
  rclcpp::executors::SingleThreadedExecutor executor_;
  std::vector<rclcpp::SubscriptionBase::SharedPtr> late_subscriptions_;
};

TEST_F(GeneratedLifecycleNode, EndpointsAppearOnlyWhileActive)
{
  wait_for_node_discovery();
  for (const auto * topic : {"/status", "/latched_status"}) {
    EXPECT_FALSE(graph_has_publisher(topic)) << topic;
  }
  for (const auto * topic : {"/cmd_vel", "/latched"}) {
    EXPECT_FALSE(graph_has_subscription(topic)) << topic;
  }

  ASSERT_EQ(node_->configure().id(), State::PRIMARY_STATE_INACTIVE);
  spin_for(300ms);
  EXPECT_FALSE(graph_has_publisher("/status"));
  EXPECT_FALSE(graph_has_subscription("/cmd_vel"));

  ASSERT_EQ(node_->activate().id(), State::PRIMARY_STATE_ACTIVE);
  EXPECT_TRUE(spin_until([this] {
    return graph_has_publisher("/status") && graph_has_publisher("/latched_status") &&
           graph_has_subscription("/cmd_vel") && graph_has_subscription("/latched");
  }));

  ASSERT_EQ(node_->deactivate().id(), State::PRIMARY_STATE_INACTIVE);
  EXPECT_TRUE(spin_until([this] {
    return !graph_has_publisher("/status") && !graph_has_publisher("/latched_status") &&
           !graph_has_subscription("/cmd_vel") && !graph_has_subscription("/latched");
  }));
  // The lifecycle interface stays.
  EXPECT_TRUE(graph_has_publisher("/cpp_lifecycle_node/transition_event"));
}

TEST_F(GeneratedLifecycleNode, PublishersExistInBothActivateAndDeactivateHooks)
{
  node_->configure();
  node_->activate();
  node_->deactivate();

  EXPECT_TRUE(node_->publishers_set_in_activate);
  EXPECT_TRUE(node_->publishers_set_in_deactivate);
}

TEST_F(GeneratedLifecycleNode, LatchedSampleFromBeforeConfigureArrivesAfterActivation)
{
  // The sample is published long before the node configures, and the node is spun the whole time.
  auto latched = peer_->create_publisher<std_msgs::msg::String>("latched", rclcpp::QoS(1).reliable().transient_local());
  std_msgs::msg::String message;
  message.data = "map";
  latched->publish(message);
  wait_for_node_discovery();

  spin_for(300ms);
  EXPECT_EQ(node_->latched_received, 0);
  ASSERT_EQ(node_->configure().id(), State::PRIMARY_STATE_INACTIVE);
  spin_for(300ms);
  EXPECT_EQ(node_->latched_received, 0);

  ASSERT_EQ(node_->activate().id(), State::PRIMARY_STATE_ACTIVE);
  EXPECT_TRUE(spin_until([this] { return 0 != node_->latched_received; }));
  spin_for(300ms);
  EXPECT_EQ(node_->latched_received, 1);
  EXPECT_EQ(node_->state_of_latched_sample, State::PRIMARY_STATE_ACTIVE);
}

TEST_F(GeneratedLifecycleNode, SubscriptionReceivesOnlyWhileActive)
{
  auto cmd_vel = peer_->create_publisher<geometry_msgs::msg::Twist>("cmd_vel", rclcpp::QoS(1).best_effort());
  node_->configure();
  spin_for(300ms);
  cmd_vel->publish(geometry_msgs::msg::Twist{});
  spin_for(300ms);
  EXPECT_EQ(node_->cmd_vel_received, 0);

  node_->activate();
  ASSERT_TRUE(spin_until([&] { return 0 != cmd_vel->get_subscription_count(); }));
  cmd_vel->publish(geometry_msgs::msg::Twist{});
  EXPECT_TRUE(spin_until([this] { return 1 == node_->cmd_vel_received; }));

  node_->deactivate();
  ASSERT_TRUE(spin_until([&] { return 0 == cmd_vel->get_subscription_count(); }));
  cmd_vel->publish(geometry_msgs::msg::Twist{});
  spin_for(300ms);
  EXPECT_EQ(node_->cmd_vel_received, 1);
}

TEST_F(GeneratedLifecycleNode, LatchedPublisherDeliversTheInitialMessageToALateSubscriber)
{
  node_->configure();
  node_->activate();

  auto received = subscribe_latched_status();

  EXPECT_TRUE(spin_until([&] { return "initial" == *received; }));
}

TEST_F(GeneratedLifecycleNode, LatchedHistoryIsLostOnDeactivationAndRepublishedOnActivation)
{
  node_->configure();
  node_->activate();
  node_->deactivate();
  ASSERT_TRUE(spin_until([this] { return !graph_has_publisher("/latched_status"); }));

  auto after_deactivation = subscribe_latched_status();
  spin_for(500ms);
  EXPECT_EQ(*after_deactivation, "");

  node_->activate();
  EXPECT_TRUE(spin_until([&] { return "initial" == *after_deactivation; }));
}

TEST_F(GeneratedLifecycleNode, DeactivateThenActivateRecreatesEverything)
{
  node_->configure();
  for (int cycle = 0; cycle < 3; ++cycle) {
    ASSERT_EQ(node_->activate().id(), State::PRIMARY_STATE_ACTIVE);
    EXPECT_TRUE(spin_until([this] { return graph_has_publisher("/status") && graph_has_subscription("/cmd_vel"); }));
    node_->publish_status();

    ASSERT_EQ(node_->deactivate().id(), State::PRIMARY_STATE_INACTIVE);
    EXPECT_TRUE(spin_until([this] { return !graph_has_publisher("/status") && !graph_has_subscription("/cmd_vel"); }));
  }
}

TEST_F(GeneratedLifecycleNode, ShutdownFromActiveDestroysTheEndpoints)
{
  node_->configure();
  node_->activate();

  ASSERT_EQ(node_->shutdown().id(), State::PRIMARY_STATE_FINALIZED);

  EXPECT_TRUE(spin_until([this] { return !graph_has_publisher("/status") && !graph_has_subscription("/cmd_vel"); }));
}

/// The node and a publisher peer spin in a multi-threaded executor while another thread cycles the node.
TEST(GeneratedLifecycleNodeThreads, CyclingUnderLoadWithAMultiThreadedExecutor)
{
  rclcpp::init(0, nullptr);
  {
    auto node = std::make_shared<TestNode>();
    auto peer = std::make_shared<rclcpp::Node>("load_peer");
    auto cmd_vel = peer->create_publisher<geometry_msgs::msg::Twist>("cmd_vel", rclcpp::QoS(1).best_effort());
    auto latched =
      peer->create_publisher<std_msgs::msg::String>("latched", rclcpp::QoS(1).reliable().transient_local());
    rclcpp::executors::MultiThreadedExecutor executor(rclcpp::ExecutorOptions(), 4);
    executor.add_node(node->get_node_base_interface());
    executor.add_node(peer);
    std::thread spinner([&executor] { executor.spin(); });

    std::atomic<bool> stop{false};
    std::thread load([&] {
      while (!stop) {
        cmd_vel->publish(geometry_msgs::msg::Twist{});
        std::this_thread::sleep_for(1ms);
      }
    });

    ASSERT_EQ(node->configure().id(), State::PRIMARY_STATE_INACTIVE);
    for (int cycle = 0; cycle < 20; ++cycle) {
      ASSERT_EQ(node->activate().id(), State::PRIMARY_STATE_ACTIVE);
      std::this_thread::sleep_for(50ms);
      ASSERT_EQ(node->deactivate().id(), State::PRIMARY_STATE_INACTIVE);
    }
    ASSERT_EQ(node->activate().id(), State::PRIMARY_STATE_ACTIVE);
    const auto deadline = std::chrono::steady_clock::now() + TIMEOUT;
    while (0 == node->cmd_vel_received && std::chrono::steady_clock::now() < deadline) {
      std::this_thread::sleep_for(10ms);
    }
    EXPECT_NE(0, node->cmd_vel_received);

    stop = true;
    load.join();
    executor.cancel();
    spinner.join();
  }
  rclcpp::shutdown();
}

}  // namespace
