// SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
// SPDX-License-Identifier: Apache-2.0
#include <gtest/gtest.h>

#include <algorithm>
#include <atomic>
#include <chrono>
#include <future>
#include <memory>
#include <string>
#include <thread>
#include <type_traits>
#include <vector>

#include "lifecycle_msgs/msg/state.hpp"
#include "lifecycle_msgs/msg/transition.hpp"
#include "lifecycle_msgs/srv/change_state.hpp"
#include "rclcpp/rclcpp.hpp"
#include "test_nodl_generators/cpp_lifecycle_node_base.hpp"

namespace
{

using std::chrono_literals::operator""ms;
using lifecycle_msgs::msg::State;
using lifecycle_msgs::msg::Transition;

const std::chrono::seconds TIMEOUT(10);
const char NODE_NAME[] = "cpp_lifecycle_node";

/// Implements only what the generated base requires, and records what the subscriptions receive.
class TestNode : public CppLifecycleNodeBase
{
  static_assert(
    std::is_base_of_v<nodl_runtime_cpp::LifecycleNode, CppLifecycleNodeBase>,
    "the lifecycle base class is the nodl runtime base class");

  static_assert(
    std::is_same_v<decltype(pub_status_), rclcpp_lifecycle::LifecyclePublisher<std_msgs::msg::String>::SharedPtr>,
    "publisher_type selects the publisher class template");

public:
  bool publisher_activated() const
  {
    return pub_status_->is_activated();
  }

  std::atomic<int> cmd_vel_received{0};
  std::atomic<int> latched_received{0};
  /// The node's state when the latched sample was executed.
  std::atomic<int> state_of_latched_sample{-1};

protected:
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

/// Spins the node and a peer on a background thread, and requests transitions through the lifecycle service.
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
    spinner_ = std::thread([this] { executor_.spin(); });
    ASSERT_TRUE(change_client_->wait_for_service(TIMEOUT));
  }

  void TearDown() override
  {
    executor_.cancel();
    spinner_.join();
  }

  /// Requests a transition, so it does not overlap the callbacks of the node.
  bool change_state(uint8_t transition_id)
  {
    auto request = std::make_shared<lifecycle_msgs::srv::ChangeState::Request>();
    request->transition.id = transition_id;
    auto response = change_client_->async_send_request(request);
    return std::future_status::ready == response.future.wait_for(TIMEOUT) && response.future.get()->success;
  }

  /// Polls until the condition holds or the timeout passes, and returns whether it holds.
  template <typename PredicateT>
  static bool wait_for(PredicateT predicate, std::chrono::milliseconds timeout = TIMEOUT)
  {
    const auto deadline = std::chrono::steady_clock::now() + timeout;
    while (!predicate() && std::chrono::steady_clock::now() < deadline) {
      std::this_thread::sleep_for(5ms);
    }
    return predicate();
  }

  /// Lets something that should not happen happen.
  static void wait_for_a_while()
  {
    std::this_thread::sleep_for(300ms);
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

  bool graph_has_service(const std::string & name)
  {
    return 0 != peer_->get_service_names_and_types_by_node(NODE_NAME, "/").count(name);
  }

  std::shared_ptr<TestNode> node_ = std::make_shared<TestNode>();
  std::shared_ptr<rclcpp::Node> peer_ = std::make_shared<rclcpp::Node>("peer_node");
  rclcpp::Client<lifecycle_msgs::srv::ChangeState>::SharedPtr change_client_ =
    peer_->create_client<lifecycle_msgs::srv::ChangeState>("/cpp_lifecycle_node/change_state");
  rclcpp::executors::SingleThreadedExecutor executor_;
  std::thread spinner_;
};

TEST_F(GeneratedLifecycleNode, SubscriptionsAppearInTheGraphOnlyWhileActive)
{
  ASSERT_TRUE(wait_for([this] { return graph_has_publisher("/cpp_lifecycle_node/transition_event"); }));
  EXPECT_FALSE(graph_has_subscription("/cmd_vel"));
  EXPECT_FALSE(graph_has_subscription("/latched"));

  ASSERT_TRUE(change_state(Transition::TRANSITION_CONFIGURE));
  wait_for_a_while();
  EXPECT_FALSE(graph_has_subscription("/cmd_vel"));
  EXPECT_FALSE(graph_has_subscription("/latched"));

  ASSERT_TRUE(change_state(Transition::TRANSITION_ACTIVATE));
  EXPECT_TRUE(wait_for([this] { return graph_has_subscription("/cmd_vel") && graph_has_subscription("/latched"); }));

  ASSERT_TRUE(change_state(Transition::TRANSITION_DEACTIVATE));
  EXPECT_TRUE(wait_for([this] { return !graph_has_subscription("/cmd_vel") && !graph_has_subscription("/latched"); }));

  ASSERT_TRUE(change_state(Transition::TRANSITION_ACTIVATE));
  EXPECT_TRUE(wait_for([this] { return graph_has_subscription("/cmd_vel") && graph_has_subscription("/latched"); }));
}

TEST_F(GeneratedLifecycleNode, PublishersAndLifecycleServicesExistInEveryState)
{
  // The publisher is a lifecycle publisher that exists from construction, and the lifecycle services do too.
  ASSERT_TRUE(
    wait_for([this] { return graph_has_publisher("/status") && graph_has_service("/cpp_lifecycle_node/get_state"); }));
  EXPECT_FALSE(node_->publisher_activated());

  ASSERT_TRUE(change_state(Transition::TRANSITION_CONFIGURE));
  ASSERT_TRUE(change_state(Transition::TRANSITION_ACTIVATE));
  EXPECT_TRUE(node_->publisher_activated());

  ASSERT_TRUE(change_state(Transition::TRANSITION_DEACTIVATE));
  EXPECT_FALSE(node_->publisher_activated());
  EXPECT_TRUE(graph_has_publisher("/status"));
  EXPECT_TRUE(graph_has_service("/cpp_lifecycle_node/get_state"));
}

TEST_F(GeneratedLifecycleNode, LatchedSampleFromBeforeConfigureArrivesAfterActivation)
{
  // The sample is published before the node configures, and the node is spinning the whole time.
  auto latched = peer_->create_publisher<std_msgs::msg::String>("latched", rclcpp::QoS(1).reliable().transient_local());
  latched->publish(std_msgs::msg::String());
  ASSERT_TRUE(wait_for([this] { return graph_has_publisher("/cpp_lifecycle_node/transition_event"); }));

  wait_for_a_while();
  EXPECT_EQ(0, node_->latched_received);
  ASSERT_TRUE(change_state(Transition::TRANSITION_CONFIGURE));
  wait_for_a_while();
  EXPECT_EQ(0, node_->latched_received);

  ASSERT_TRUE(change_state(Transition::TRANSITION_ACTIVATE));
  EXPECT_TRUE(wait_for([this] { return 0 != node_->latched_received; }));
  wait_for_a_while();
  EXPECT_EQ(1, node_->latched_received);
  EXPECT_EQ(State::PRIMARY_STATE_ACTIVE, node_->state_of_latched_sample);

  // Activating again creates a new subscription, which gets the latched sample again.
  ASSERT_TRUE(change_state(Transition::TRANSITION_DEACTIVATE));
  wait_for_a_while();
  EXPECT_EQ(1, node_->latched_received);
  ASSERT_TRUE(change_state(Transition::TRANSITION_ACTIVATE));
  EXPECT_TRUE(wait_for([this] { return 2 == node_->latched_received; }));
}

TEST_F(GeneratedLifecycleNode, SubscriptionReceivesOnlyWhileActive)
{
  auto cmd_vel = peer_->create_publisher<geometry_msgs::msg::Twist>("cmd_vel", rclcpp::QoS(1).best_effort());
  ASSERT_TRUE(change_state(Transition::TRANSITION_CONFIGURE));
  cmd_vel->publish(geometry_msgs::msg::Twist{});
  wait_for_a_while();
  EXPECT_EQ(0, node_->cmd_vel_received);

  ASSERT_TRUE(change_state(Transition::TRANSITION_ACTIVATE));
  ASSERT_TRUE(wait_for([&] { return 0 != cmd_vel->get_subscription_count(); }));
  cmd_vel->publish(geometry_msgs::msg::Twist{});
  EXPECT_TRUE(wait_for([this] { return 1 == node_->cmd_vel_received; }));

  ASSERT_TRUE(change_state(Transition::TRANSITION_DEACTIVATE));
  ASSERT_TRUE(wait_for([&] { return 0 == cmd_vel->get_subscription_count(); }));
  cmd_vel->publish(geometry_msgs::msg::Twist{});
  wait_for_a_while();
  EXPECT_EQ(1, node_->cmd_vel_received);
}

TEST_F(GeneratedLifecycleNode, ShutdownFromActiveDestroysTheSubscriptions)
{
  ASSERT_TRUE(change_state(Transition::TRANSITION_CONFIGURE));
  ASSERT_TRUE(change_state(Transition::TRANSITION_ACTIVATE));
  ASSERT_TRUE(wait_for([this] { return graph_has_subscription("/cmd_vel"); }));

  ASSERT_TRUE(change_state(Transition::TRANSITION_ACTIVE_SHUTDOWN));

  EXPECT_TRUE(wait_for([this] { return !graph_has_subscription("/cmd_vel") && !graph_has_subscription("/latched"); }));
}

}  // namespace
