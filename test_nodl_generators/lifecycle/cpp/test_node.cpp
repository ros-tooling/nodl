// SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
// SPDX-License-Identifier: Apache-2.0
#include <gtest/gtest.h>

#include <atomic>
#include <chrono>
#include <future>
#include <memory>
#include <type_traits>
#include <vector>

#include "example_interfaces/action/fibonacci.hpp"
#include "example_interfaces/srv/add_two_ints.hpp"
#include "geometry_msgs/msg/twist.hpp"
#include "lifecycle_msgs/msg/state.hpp"
#include "nodl_runtime_cpp/gate.hpp"
#include "rclcpp/rclcpp.hpp"
#include "rclcpp_action/rclcpp_action.hpp"
#include "std_srvs/srv/trigger.hpp"
#include "test_nodl_generators/cpp_lifecycle_node_base.hpp"

namespace
{

using AddTwoInts = example_interfaces::srv::AddTwoInts;
using Fibonacci = example_interfaces::action::Fibonacci;
using std::chrono_literals::operator""ms;
using std::chrono_literals::operator""s;

/// Implements only what the generated base requires, publishes from `handle_activate`, and counts its callbacks.
/// It also records `gain` where each hook sees it, and the values that `on_parameters_changed` receives.
/// It also sends from both client kinds in `handle_configure` and `handle_activate`, and keeps what happened.
/// Its action server never works on a goal, and `handle_deactivate` succeeds only the goals of order 1.
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

  /// Whether the service and the action server that the clients send to are discovered.
  bool clients_ready() const
  {
    return cli_add_->service_is_ready() && action_cli_fibonacci_->action_server_is_ready();
  }

  double gain() const
  {
    return params_.lock()->gain;
  }

protected:
  CallbackReturn handle_configure(const rclcpp_lifecycle::State &) override
  {
    gain_in_configure = gain();
    // Waiting is allowed, sending is not.
    waiting_in_configure_threw = false;
    try {
      cli_add_->wait_for_service(0ms);
      cli_add_->service_is_ready();
      action_cli_fibonacci_->wait_for_action_server(0ms);
    } catch (const nodl_runtime_cpp::InactiveError &) {
      waiting_in_configure_threw = true;
    }
    service_send_in_configure_threw =
      throws_inactive([this] { cli_add_->async_send_request(std::make_shared<AddTwoInts::Request>()); });
    action_send_in_configure_threw =
      throws_inactive([this] { action_cli_fibonacci_->async_send_goal(Fibonacci::Goal()); });
    return CallbackReturn::SUCCESS;
  }

  CallbackReturn handle_activate(const rclcpp_lifecycle::State &) override
  {
    gain_in_activate = gain();
    publish_status();
    auto request = std::make_shared<AddTwoInts::Request>();
    request->a = 2;
    request->b = 3;
    activate_sum = cli_add_->async_send_request(request).future.share();
    activate_goal_handle = action_cli_fibonacci_->async_send_goal(Fibonacci::Goal());
    return CallbackReturn::SUCCESS;
  }

  CallbackReturn handle_deactivate(const rclcpp_lifecycle::State &) override
  {
    for (const auto & goal_handle : count_goals) {
      if (1 == goal_handle->get_goal()->order) {
        goal_handle->succeed(std::make_shared<Fibonacci::Result>());
      }
    }
    return CallbackReturn::SUCCESS;
  }

  void on_parameters_changed(const cpp_lifecycle_node_base::Params & params) override
  {
    notified_gains.push_back(params.gain);
  }

  rclcpp_action::GoalResponse on_count_goal(
    const rclcpp_action::GoalUUID &, std::shared_ptr<const Fibonacci::Goal>) override
  {
    return rclcpp_action::GoalResponse::ACCEPT_AND_EXECUTE;
  }

  rclcpp_action::CancelResponse on_count_cancel(std::shared_ptr<rclcpp_action::ServerGoalHandle<Fibonacci>>) override
  {
    return rclcpp_action::CancelResponse::ACCEPT;
  }

  void on_count_accepted(std::shared_ptr<rclcpp_action::ServerGoalHandle<Fibonacci>> goal_handle) override
  {
    count_goals.push_back(goal_handle);
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
  double gain_in_configure = 0.0;
  double gain_in_activate = 0.0;
  std::vector<double> notified_gains;
  std::atomic<int> cmd_vel_count{0};
  std::vector<std::shared_ptr<rclcpp_action::ServerGoalHandle<Fibonacci>>> count_goals;
  bool waiting_in_configure_threw = true;
  bool service_send_in_configure_threw = false;
  bool action_send_in_configure_threw = false;
  std::shared_future<AddTwoInts::Response::SharedPtr> activate_sum;
  std::shared_future<rclcpp_action::ClientGoalHandle<Fibonacci>::SharedPtr> activate_goal_handle;

private:
  template <typename F>
  static bool throws_inactive(F && send)
  {
    try {
      send();
    } catch (const nodl_runtime_cpp::InactiveError &) {
      return true;
    }
    return false;
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

  /// A peer that answers the node's clients.
  void serve_clients()
  {
    add_service_ = peer_->create_service<AddTwoInts>(
      "add", [](AddTwoInts::Request::SharedPtr request, AddTwoInts::Response::SharedPtr response) {
        response->sum = request->a + request->b;
      });
    fibonacci_server_ = rclcpp_action::create_server<Fibonacci>(
      peer_,
      "fibonacci",
      [](const rclcpp_action::GoalUUID &, std::shared_ptr<const Fibonacci::Goal>) {
        return rclcpp_action::GoalResponse::ACCEPT_AND_EXECUTE;
      },
      [](std::shared_ptr<rclcpp_action::ServerGoalHandle<Fibonacci>>) { return rclcpp_action::CancelResponse::ACCEPT; },
      [](std::shared_ptr<rclcpp_action::ServerGoalHandle<Fibonacci>> goal_handle) {
        goal_handle->succeed(std::make_shared<Fibonacci::Result>());
      });
    const auto deadline = std::chrono::steady_clock::now() + 5s;
    while (!node_->clients_ready() && std::chrono::steady_clock::now() < deadline) {
      executor_.spin_some(10ms);
    }
  }

  std::shared_ptr<TestNode> node_ = std::make_shared<TestNode>();
  std::shared_ptr<rclcpp::Node> peer_ = std::make_shared<rclcpp::Node>("peer_node");
  rclcpp::Subscription<std_msgs::msg::String>::SharedPtr subscription_;
  rclcpp::Publisher<geometry_msgs::msg::Twist>::SharedPtr publisher_ =
    peer_->create_publisher<geometry_msgs::msg::Twist>("cmd_vel", rclcpp::QoS(1).best_effort());
  rclcpp::Client<std_srvs::srv::Trigger>::SharedPtr client_ = peer_->create_client<std_srvs::srv::Trigger>("trigger");
  rclcpp::Service<AddTwoInts>::SharedPtr add_service_;
  rclcpp_action::Server<Fibonacci>::SharedPtr fibonacci_server_;
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

TEST_F(GeneratedLifecycleNode, SendsFromClientsOnlyOnceTheGateIsOpen)
{
  serve_clients();

  node_->configure();
  EXPECT_FALSE(node_->waiting_in_configure_threw);
  EXPECT_TRUE(node_->service_send_in_configure_threw);
  EXPECT_TRUE(node_->action_send_in_configure_threw);

  node_->activate();
  ASSERT_EQ(executor_.spin_until_future_complete(node_->activate_sum, 5s), rclcpp::FutureReturnCode::SUCCESS);
  EXPECT_EQ(node_->activate_sum.get()->sum, 5);
  ASSERT_EQ(executor_.spin_until_future_complete(node_->activate_goal_handle, 5s), rclcpp::FutureReturnCode::SUCCESS);
  EXPECT_NE(node_->activate_goal_handle.get(), nullptr);
}

TEST_F(GeneratedLifecycleNode, EndsActionGoalsOnDeactivationAfterTheHook)
{
  auto action_client = rclcpp_action::create_client<Fibonacci>(peer_, "count");
  const auto deadline = std::chrono::steady_clock::now() + 5s;
  while (!action_client->action_server_is_ready() && std::chrono::steady_clock::now() < deadline) {
    executor_.spin_some(10ms);
  }
  const auto send = [&](int32_t order) {
    Fibonacci::Goal goal;
    goal.order = order;
    auto handle_future = action_client->async_send_goal(goal);
    EXPECT_EQ(executor_.spin_until_future_complete(handle_future, 5s), rclcpp::FutureReturnCode::SUCCESS);
    return handle_future.get();
  };

  // Rejected while unconfigured and inactive.
  EXPECT_EQ(send(0), nullptr);
  node_->configure();
  EXPECT_EQ(send(0), nullptr);

  node_->activate();
  auto abandoned = send(0);
  auto finished_by_hook = send(1);
  ASSERT_NE(abandoned, nullptr);
  ASSERT_NE(finished_by_hook, nullptr);
  auto abandoned_result = action_client->async_get_result(abandoned);
  auto finished_result = action_client->async_get_result(finished_by_hook);

  node_->deactivate();

  ASSERT_EQ(executor_.spin_until_future_complete(abandoned_result, 5s), rclcpp::FutureReturnCode::SUCCESS);
  EXPECT_EQ(abandoned_result.get().code, rclcpp_action::ResultCode::ABORTED);
  ASSERT_EQ(executor_.spin_until_future_complete(finished_result, 5s), rclcpp::FutureReturnCode::SUCCESS);
  EXPECT_EQ(finished_result.get().code, rclcpp_action::ResultCode::SUCCEEDED);
}

TEST_F(GeneratedLifecycleNode, RefreshesParametersSetWhileUnconfiguredAtConfigure)
{
  ASSERT_TRUE(node_->set_parameter(rclcpp::Parameter("gain", 2.0)).successful);
  EXPECT_DOUBLE_EQ(node_->gain(), 1.0);

  node_->configure();

  EXPECT_DOUBLE_EQ(node_->gain_in_configure, 2.0);
  EXPECT_TRUE(node_->notified_gains.empty());
}

TEST_F(GeneratedLifecycleNode, RefreshesParametersSetWhileInactiveAtActivate)
{
  node_->configure();
  node_->activate();
  node_->deactivate();
  ASSERT_TRUE(node_->set_parameter(rclcpp::Parameter("gain", 3.0)).successful);
  EXPECT_DOUBLE_EQ(node_->gain(), 1.0);

  node_->activate();

  EXPECT_DOUBLE_EQ(node_->gain_in_activate, 3.0);
  EXPECT_TRUE(node_->notified_gains.empty());
}

TEST_F(GeneratedLifecycleNode, FollowsParameterChangesOnlyWhileActive)
{
  node_->configure();
  ASSERT_TRUE(node_->set_parameter(rclcpp::Parameter("gain", 2.0)).successful);
  EXPECT_DOUBLE_EQ(node_->gain(), 1.0);

  node_->activate();
  ASSERT_TRUE(node_->set_parameter(rclcpp::Parameter("gain", 4.0)).successful);
  EXPECT_DOUBLE_EQ(node_->gain(), 4.0);
  EXPECT_EQ(node_->notified_gains, std::vector<double>{4.0});

  node_->deactivate();
  ASSERT_TRUE(node_->set_parameter(rclcpp::Parameter("gain", 5.0)).successful);
  EXPECT_DOUBLE_EQ(node_->gain(), 4.0);
  EXPECT_EQ(node_->notified_gains, std::vector<double>{4.0});
}

}  // namespace
