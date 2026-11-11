// SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
// SPDX-License-Identifier: Apache-2.0
#include <gtest/gtest.h>

#include <algorithm>
#include <atomic>
#include <chrono>
#include <functional>
#include <future>
#include <memory>
#include <mutex>
#include <optional>
#include <string>
#include <thread>
#include <type_traits>
#include <vector>

#include "example_interfaces/action/fibonacci.hpp"
#include "lifecycle_msgs/msg/state.hpp"
#include "lifecycle_msgs/msg/transition.hpp"
#include "lifecycle_msgs/srv/change_state.hpp"
#include "rclcpp/rclcpp.hpp"
#include "rclcpp_action/rclcpp_action.hpp"
#include "std_srvs/srv/set_bool.hpp"
#include "std_srvs/srv/trigger.hpp"
#include "test_nodl_generators/cpp_lifecycle_node_base.hpp"

namespace
{

using std::chrono_literals::operator""ms;
using lifecycle_msgs::msg::State;
using lifecycle_msgs::msg::Transition;

/// Requests a transition through the lifecycle service, which an executor serializes with the default-group callbacks.
bool change_state(const rclcpp::Client<lifecycle_msgs::srv::ChangeState>::SharedPtr & client, uint8_t transition_id)
{
  auto request = std::make_shared<lifecycle_msgs::srv::ChangeState::Request>();
  request->transition.id = transition_id;
  auto response = client->async_send_request(request);
  return std::future_status::ready == response.future.wait_for(std::chrono::seconds(10)) &&
         response.future.get()->success;
}

using Fibonacci = example_interfaces::action::Fibonacci;
using FibonacciGoalHandle = rclcpp_action::ServerGoalHandle<Fibonacci>;

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

  /// Sends a request on the set_bool client, which must exist.
  rclcpp::Client<std_srvs::srv::SetBool>::FutureAndRequestId send_set_bool()
  {
    return cli_set_bool_->async_send_request(std::make_shared<std_srvs::srv::SetBool::Request>());
  }

  /// Sends a goal on the remote_fibonacci client, which must exist.
  std::shared_future<rclcpp_action::Client<Fibonacci>::GoalHandle::SharedPtr> send_remote_goal()
  {
    return action_cli_remote_fibonacci_->async_send_goal(Fibonacci::Goal());
  }

  /// Returns the goal that the fibonacci action server accepted at `index`, or null.
  std::shared_ptr<FibonacciGoalHandle> accepted_goal(size_t index)
  {
    std::lock_guard<std::mutex> lock(goals_mutex_);
    return index < goals_.size() ? goals_[index] : nullptr;
  }

  size_t accepted_goal_count()
  {
    std::lock_guard<std::mutex> lock(goals_mutex_);
    return goals_.size();
  }

  /// Makes `handle_activate` wait for the remote_fibonacci server and send it a goal.
  std::atomic<bool> send_goal_in_activate{false};
  std::atomic<bool> goal_accepted_in_activate{false};
  /// Makes `handle_activate` wait for the set_bool service and call it.
  std::atomic<bool> call_set_bool_in_activate{false};
  std::atomic<bool> set_bool_answered_in_activate{false};
  /// Whether the generated publishers existed when each hook ran.
  std::atomic<bool> publishers_set_in_activate{false};
  std::atomic<bool> publishers_set_in_deactivate{false};
  std::atomic<int> deactivate_hook_calls{0};
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
    if (send_goal_in_activate) {
      goal_accepted_in_activate = action_cli_remote_fibonacci_->wait_for_action_server(TIMEOUT) &&
                                  std::future_status::ready == send_remote_goal().wait_for(TIMEOUT);
    }
    if (call_set_bool_in_activate) {
      set_bool_answered_in_activate = cli_set_bool_->wait_for_service(TIMEOUT) &&
                                      std::future_status::ready == send_set_bool().future.wait_for(TIMEOUT);
    }
    return CallbackReturn::SUCCESS;
  }

  CallbackReturn handle_deactivate(const rclcpp_lifecycle::State &) override
  {
    publishers_set_in_deactivate = (nullptr != pub_status_);
    ++deactivate_hook_calls;
    return CallbackReturn::SUCCESS;
  }

  void on_cmd_vel(geometry_msgs::msg::Twist::ConstSharedPtr /*msg*/) override
  {
    ++cmd_vel_received;
  }

  void on_trigger(
    std_srvs::srv::Trigger::Request::SharedPtr /*request*/,
    std_srvs::srv::Trigger::Response::SharedPtr response) override
  {
    response->success = true;
  }

  rclcpp_action::GoalResponse on_fibonacci_goal(
    const rclcpp_action::GoalUUID & /*uuid*/, std::shared_ptr<const Fibonacci::Goal> /*goal*/) override
  {
    return rclcpp_action::GoalResponse::ACCEPT_AND_EXECUTE;
  }

  rclcpp_action::CancelResponse on_fibonacci_cancel(std::shared_ptr<FibonacciGoalHandle> /*goal_handle*/) override
  {
    return rclcpp_action::CancelResponse::ACCEPT;
  }

  void on_fibonacci_accepted(std::shared_ptr<FibonacciGoalHandle> goal_handle) override
  {
    std::lock_guard<std::mutex> lock(goals_mutex_);
    goals_.push_back(goal_handle);
  }

  void on_latched(std_msgs::msg::String::ConstSharedPtr /*msg*/) override
  {
    state_of_latched_sample = get_current_state().id();
    ++latched_received;
  }

private:
  std::mutex goals_mutex_;
  std::vector<std::shared_ptr<FibonacciGoalHandle>> goals_;
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

  bool graph_has_service(const std::string & name)
  {
    return 0 != peer_->get_service_names_and_types_by_node(NODE_NAME, "/").count(name);
  }

  bool graph_has_client(const std::string & name)
  {
    return 0 != peer_->get_node_graph_interface()->get_client_names_and_types_by_node(NODE_NAME, "/").count(name);
  }

  bool graph_has_action_server(const std::string & name)
  {
    return graph_has_service("/" + name + "/_action/send_goal");
  }

  bool graph_has_action_client(const std::string & name)
  {
    return graph_has_client("/" + name + "/_action/send_goal");
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

  EXPECT_FALSE(graph_has_service("/trigger"));
  EXPECT_FALSE(graph_has_client("/set_bool"));
  EXPECT_FALSE(graph_has_action_server("fibonacci"));
  EXPECT_FALSE(graph_has_action_client("remote_fibonacci"));
  // The lifecycle and parameter services stay.
  EXPECT_TRUE(graph_has_service("/cpp_lifecycle_node/get_state"));

  ASSERT_EQ(node_->configure().id(), State::PRIMARY_STATE_INACTIVE);
  spin_for(300ms);
  EXPECT_FALSE(graph_has_publisher("/status"));
  EXPECT_FALSE(graph_has_subscription("/cmd_vel"));
  EXPECT_FALSE(graph_has_service("/trigger"));

  ASSERT_EQ(node_->activate().id(), State::PRIMARY_STATE_ACTIVE);
  EXPECT_TRUE(spin_until([this] {
    return graph_has_publisher("/status") && graph_has_publisher("/latched_status") &&
           graph_has_subscription("/cmd_vel") && graph_has_subscription("/latched") && graph_has_service("/trigger") &&
           graph_has_client("/set_bool") && graph_has_action_server("fibonacci") &&
           graph_has_action_client("remote_fibonacci");
  }));

  ASSERT_EQ(node_->deactivate().id(), State::PRIMARY_STATE_INACTIVE);
  EXPECT_TRUE(spin_until([this] {
    return !graph_has_publisher("/status") && !graph_has_publisher("/latched_status") &&
           !graph_has_subscription("/cmd_vel") && !graph_has_subscription("/latched") &&
           !graph_has_service("/trigger") && !graph_has_client("/set_bool") && !graph_has_action_server("fibonacci") &&
           !graph_has_action_client("remote_fibonacci");
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

TEST_F(GeneratedLifecycleNode, ShutdownFromActiveRunsHandleDeactivateAndDestroysTheEndpoints)
{
  node_->configure();
  node_->activate();

  ASSERT_EQ(node_->shutdown().id(), State::PRIMARY_STATE_FINALIZED);

  EXPECT_EQ(node_->deactivate_hook_calls, 1);
  EXPECT_TRUE(spin_until([this] {
    return !graph_has_publisher("/status") && !graph_has_subscription("/cmd_vel") && !graph_has_service("/trigger") &&
           !graph_has_action_server("fibonacci") && !graph_has_action_client("remote_fibonacci");
  }));
}

/// A fixture that spins the node and a peer on a background thread, so a transition can wait for a response.
class GeneratedLifecycleNodeSpinning : public ::testing::Test
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

  /// Requests a transition through the lifecycle service.
  /// Calling `activate()` and `deactivate()` from this thread instead resets the members while callbacks run.
  bool change_state(uint8_t transition_id)
  {
    return ::change_state(change_client_, transition_id);
  }

  std::shared_ptr<TestNode> node_ = std::make_shared<TestNode>();
  std::shared_ptr<rclcpp::Node> peer_ = std::make_shared<rclcpp::Node>("peer_node");
  rclcpp::Client<lifecycle_msgs::srv::ChangeState>::SharedPtr change_client_ =
    peer_->create_client<lifecycle_msgs::srv::ChangeState>("/cpp_lifecycle_node/change_state");
  /// A single-threaded executor, since an action endpoint destroyed under a multi-threaded executor can deadlock in rclcpp.
  rclcpp::executors::SingleThreadedExecutor executor_;
  std::thread spinner_;
};

TEST_F(GeneratedLifecycleNodeSpinning, ServiceIsNotDiscoverableWhileInactiveAndAnswersWhenActive)
{
  auto trigger = peer_->create_client<std_srvs::srv::Trigger>("trigger");
  EXPECT_FALSE(trigger->wait_for_service(500ms));
  ASSERT_TRUE(change_state(Transition::TRANSITION_CONFIGURE));
  EXPECT_FALSE(trigger->wait_for_service(500ms));

  ASSERT_TRUE(change_state(Transition::TRANSITION_ACTIVATE));
  ASSERT_TRUE(trigger->wait_for_service(TIMEOUT));
  auto response = trigger->async_send_request(std::make_shared<std_srvs::srv::Trigger::Request>());
  ASSERT_EQ(std::future_status::ready, response.future.wait_for(TIMEOUT));
  EXPECT_TRUE(response.future.get()->success);

  ASSERT_TRUE(change_state(Transition::TRANSITION_DEACTIVATE));
  const auto deadline = std::chrono::steady_clock::now() + TIMEOUT;
  while (trigger->service_is_ready() && std::chrono::steady_clock::now() < deadline) {
    std::this_thread::sleep_for(10ms);
  }
  EXPECT_FALSE(trigger->service_is_ready());
}

TEST_F(GeneratedLifecycleNodeSpinning, ClientCreatedAtActivationIsUsableFromHandleActivate)
{
  // The hook waits for a response, so the transition runs on this thread and not in the executor.
  auto set_bool = peer_->create_service<std_srvs::srv::SetBool>(
    "set_bool", [](std_srvs::srv::SetBool::Request::SharedPtr, std_srvs::srv::SetBool::Response::SharedPtr response) {
      response->success = true;
    });
  node_->call_set_bool_in_activate = true;
  ASSERT_EQ(node_->configure().id(), State::PRIMARY_STATE_INACTIVE);

  ASSERT_EQ(node_->activate().id(), State::PRIMARY_STATE_ACTIVE);

  EXPECT_TRUE(node_->set_bool_answered_in_activate);
}

TEST_F(GeneratedLifecycleNodeSpinning, PendingRequestFailsWhenTheNodeDeactivates)
{
  // No peer serves set_bool, so the request stays pending.
  ASSERT_TRUE(change_state(Transition::TRANSITION_CONFIGURE));
  ASSERT_TRUE(change_state(Transition::TRANSITION_ACTIVATE));
  auto pending = node_->send_set_bool();
  ASSERT_EQ(std::future_status::timeout, pending.future.wait_for(200ms));

  ASSERT_TRUE(change_state(Transition::TRANSITION_DEACTIVATE));

  EXPECT_THROW(pending.future.get(), std::future_error);
}

TEST_F(GeneratedLifecycleNodeSpinning, GoalActiveAtDeactivationEndsAbortedAndTheClientGetsItsResult)
{
  auto client = rclcpp_action::create_client<Fibonacci>(peer_, "fibonacci");
  ASSERT_TRUE(change_state(Transition::TRANSITION_CONFIGURE));
  EXPECT_FALSE(client->wait_for_action_server(500ms));

  // The server never answers a result request that it has not taken when it is destroyed, so the scenario is repeated
  // until the client gets the result.
  std::optional<rclcpp_action::ResultCode> code;
  for (int attempt = 0; attempt < 40 && !code; ++attempt) {
    ASSERT_TRUE(change_state(Transition::TRANSITION_ACTIVATE));
    ASSERT_TRUE(client->wait_for_action_server(TIMEOUT));
    const auto count = node_->accepted_goal_count();
    auto sent = client->async_send_goal(Fibonacci::Goal());
    ASSERT_EQ(std::future_status::ready, sent.wait_for(TIMEOUT));
    auto result = client->async_get_result(sent.get());
    const auto deadline = std::chrono::steady_clock::now() + TIMEOUT;
    while (count == node_->accepted_goal_count() && std::chrono::steady_clock::now() < deadline) {
      std::this_thread::sleep_for(1ms);
    }
    ASSERT_LT(count, node_->accepted_goal_count());
    ASSERT_TRUE(node_->accepted_goal(count)->is_executing());

    ASSERT_TRUE(change_state(Transition::TRANSITION_DEACTIVATE));

    EXPECT_FALSE(node_->accepted_goal(count)->is_active());
    if (std::future_status::ready == result.wait_for(500ms)) {
      code = result.get().code;
    }
  }

  ASSERT_TRUE(code.has_value()) << "The client never got a result";
  EXPECT_EQ(rclcpp_action::ResultCode::ABORTED, *code);
}

TEST_F(GeneratedLifecycleNodeSpinning, ResultMayStayUnansweredAndTheClientTimesOutCleanly)
{
  auto client = rclcpp_action::create_client<Fibonacci>(peer_, "fibonacci");
  ASSERT_TRUE(change_state(Transition::TRANSITION_CONFIGURE));
  ASSERT_TRUE(change_state(Transition::TRANSITION_ACTIVATE));
  ASSERT_TRUE(client->wait_for_action_server(TIMEOUT));
  auto sent = client->async_send_goal(Fibonacci::Goal());
  ASSERT_EQ(std::future_status::ready, sent.wait_for(TIMEOUT));
  auto result = client->async_get_result(sent.get());

  ASSERT_TRUE(change_state(Transition::TRANSITION_DEACTIVATE));

  // Either the server took the result request before it was destroyed, or nothing answers it.
  if (std::future_status::ready == result.wait_for(1000ms)) {
    EXPECT_EQ(rclcpp_action::ResultCode::ABORTED, result.get().code);
  }
  const auto deadline = std::chrono::steady_clock::now() + TIMEOUT;
  while (client->action_server_is_ready() && std::chrono::steady_clock::now() < deadline) {
    std::this_thread::sleep_for(10ms);
  }
  EXPECT_FALSE(client->action_server_is_ready());
}

TEST_F(GeneratedLifecycleNodeSpinning, ActionClientCreatedAtActivationIsUsableFromHandleActivate)
{
  // The hook waits for a response, so the transition runs on this thread and not in the executor.
  auto server = rclcpp_action::create_server<Fibonacci>(
    peer_,
    "remote_fibonacci",
    [](const rclcpp_action::GoalUUID &, std::shared_ptr<const Fibonacci::Goal>) {
      return rclcpp_action::GoalResponse::ACCEPT_AND_EXECUTE;
    },
    [](std::shared_ptr<FibonacciGoalHandle>) { return rclcpp_action::CancelResponse::ACCEPT; },
    [](std::shared_ptr<FibonacciGoalHandle> goal_handle) {
      std::thread([goal_handle] { goal_handle->succeed(std::make_shared<Fibonacci::Result>()); }).detach();
    });
  node_->send_goal_in_activate = true;
  ASSERT_EQ(node_->configure().id(), State::PRIMARY_STATE_INACTIVE);

  ASSERT_EQ(node_->activate().id(), State::PRIMARY_STATE_ACTIVE);

  EXPECT_TRUE(node_->goal_accepted_in_activate);
}

TEST_F(GeneratedLifecycleNodeSpinning, PendingGoalFailsWhenTheNodeDeactivates)
{
  // No peer serves remote_fibonacci, so the goal request stays pending.
  ASSERT_TRUE(change_state(Transition::TRANSITION_CONFIGURE));
  ASSERT_TRUE(change_state(Transition::TRANSITION_ACTIVATE));
  auto pending = node_->send_remote_goal();
  ASSERT_EQ(std::future_status::timeout, pending.wait_for(200ms));

  ASSERT_TRUE(change_state(Transition::TRANSITION_DEACTIVATE));

  EXPECT_THROW(pending.get(), std::future_error);
}

}  // namespace
