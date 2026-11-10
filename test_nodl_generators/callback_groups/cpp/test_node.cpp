// SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
// SPDX-License-Identifier: Apache-2.0
#include <atomic>
#include <chrono>
#include <future>
#include <memory>
#include <mutex>
#include <string>
#include <thread>
#include <type_traits>
#include <utility>

#include "gtest/gtest.h"
#include "lifecycle_msgs/msg/state.hpp"
#include "rclcpp/rclcpp.hpp"
#include "test_nodl_generators/callback_defaults_base.hpp"
#include "test_nodl_generators/callback_lifecycle_base.hpp"
#include "test_nodl_generators/callback_reentrant_base.hpp"
#include "test_nodl_generators/callback_separate_base.hpp"
#include "test_nodl_generators/callback_shared_base.hpp"

using std::chrono_literals::operator""ms;
using std::chrono_literals::operator""s;
using Work = std_msgs::msg::Empty;
using Status = std_srvs::srv::Trigger;
using LifecycleState = lifecycle_msgs::msg::State;

namespace
{

struct WorkState
{
  std::promise<void> entered;
  std::promise<void> entered_twice;
  std::promise<void> release;
  std::shared_future<void> released = release.get_future().share();
  std::atomic<int> calls{0};
  std::once_flag release_once;

  void release_work()
  {
    std::call_once(release_once, [this]() { release.set_value(); });
  }
};

template <typename Base>
class Processor : public Base
{
  template <typename T>
  static auto detect_gate(int) -> decltype(std::declval<T &>().gate(), std::true_type{});
  template <typename>
  static auto detect_gate(...) -> std::false_type;

public:
  // The upstream gated base is optional until its lifecycle stack merges.
  static constexpr bool activation_gated = decltype(detect_gate<Processor>(0))::value;

  Processor(const rclcpp::NodeOptions & options, std::shared_ptr<WorkState> state)
  : Base(options)
  , state_(std::move(state))
  {}

private:
  void on_work(Work::ConstSharedPtr) override
  {
    const auto calls = state_->calls.fetch_add(1);
    if (calls == 0) {
      state_->entered.set_value();
    } else if (calls == 1) {
      state_->entered_twice.set_value();
    }
    state_->released.wait_for(10s);
  }

  void on_status(Status::Request::SharedPtr, Status::Response::SharedPtr response) override
  {
    response->success = true;
  }

  std::shared_ptr<WorkState> state_;
};

class RunningExecutor
{
public:
  explicit RunningExecutor(std::shared_ptr<WorkState> state)
  : executor_(rclcpp::ExecutorOptions(), 3)
  , state_(std::move(state))
  {}

  template <typename Node>
  void start(const std::shared_ptr<Node> & processor, const rclcpp::Node::SharedPtr & driver)
  {
    executor_.add_node(processor->get_node_base_interface());
    executor_.add_node(driver);
    thread_ = std::thread([this]() { executor_.spin(); });
  }

  ~RunningExecutor()
  {
    // A failed assertion must also unblock worker threads before joining.
    state_->release_work();
    executor_.cancel();
    if (thread_.joinable()) {
      thread_.join();
    }
  }

private:
  rclcpp::executors::MultiThreadedExecutor executor_;
  std::shared_ptr<WorkState> state_;
  std::thread thread_;
};

class CallbackGroups : public testing::Test
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

  rclcpp::NodeOptions node_options()
  {
    // Avoid sharing topics with other ROS integration tests in colcon's parallel run.
    const auto stamp = std::chrono::steady_clock::now().time_since_epoch().count();
    return rclcpp::NodeOptions().arguments(
      {"--ros-args", "-r", "__ns:=/nodl_callback_groups_" + std::to_string(stamp)});
  }

  template <typename Base>
  void check(bool concurrent, bool reentrant = false)
  {
    auto state = std::make_shared<WorkState>();
    auto entered = state->entered.get_future();
    auto entered_twice = state->entered_twice.get_future();
    auto options = node_options();
    auto processor = std::make_shared<Processor<Base>>(options, state);
    exercise(processor, options, state, entered, entered_twice, concurrent, reentrant);
  }

  template <typename Node>
  void exercise(
    const std::shared_ptr<Node> & processor,
    const rclcpp::NodeOptions & options,
    const std::shared_ptr<WorkState> & state,
    std::future<void> & entered,
    std::future<void> & entered_twice,
    bool concurrent,
    bool reentrant = false)
  {
    auto driver = std::make_shared<rclcpp::Node>("driver", options);
    auto publisher = driver->create_publisher<Work>("work", 10);
    auto client = driver->create_client<Status>("status");
    RunningExecutor running(state);
    running.start(processor, driver);

    ASSERT_TRUE(client->wait_for_service(5s));
    const auto deadline = std::chrono::steady_clock::now() + 5s;
    while (publisher->get_subscription_count() == 0 && std::chrono::steady_clock::now() < deadline) {
      std::this_thread::sleep_for(10ms);
    }
    ASSERT_EQ(publisher->get_subscription_count(), 1u);
    publisher->publish(Work{});
    ASSERT_EQ(entered.wait_for(5s), std::future_status::ready);

    if (reentrant) {
      publisher->publish(Work{});
      ASSERT_EQ(entered_twice.wait_for(3s), std::future_status::ready);
    } else {
      auto response = client->async_send_request(std::make_shared<Status::Request>());
      const auto ready = response.wait_for(concurrent ? 3s : 300ms);
      EXPECT_EQ(ready == std::future_status::ready, concurrent);
      state->release_work();
      ASSERT_EQ(response.wait_for(3s), std::future_status::ready);
      EXPECT_TRUE(response.get()->success);
    }
  }
};

TEST_F(CallbackGroups, DefaultsSerialize)
{
  check<CallbackDefaultsBase>(false);
}

TEST_F(CallbackGroups, SharedGroupSerializes)
{
  check<CallbackSharedBase>(false);
}

TEST_F(CallbackGroups, SeparateGroupsAllowProgress)
{
  check<CallbackSeparateBase>(true);
}

TEST_F(CallbackGroups, ReentrantSubscriptionOverlapsItself)
{
  check<CallbackReentrantBase>(true, true);
}

TEST_F(CallbackGroups, LifecycleKeepsGroupsAcrossTransitions)
{
  auto options = node_options();
  auto state = std::make_shared<WorkState>();
  auto entered = state->entered.get_future();
  auto entered_twice = state->entered_twice.get_future();
  auto processor = std::make_shared<Processor<CallbackLifecycleBase>>(options, state);
  ASSERT_EQ(processor->configure().id(), LifecycleState::PRIMARY_STATE_INACTIVE);
  ASSERT_EQ(processor->activate().id(), LifecycleState::PRIMARY_STATE_ACTIVE);
  ASSERT_EQ(processor->deactivate().id(), LifecycleState::PRIMARY_STATE_INACTIVE);
  ASSERT_EQ(processor->cleanup().id(), LifecycleState::PRIMARY_STATE_UNCONFIGURED);
  ASSERT_EQ(processor->configure().id(), LifecycleState::PRIMARY_STATE_INACTIVE);
  ASSERT_EQ(processor->activate().id(), LifecycleState::PRIMARY_STATE_ACTIVE);
  exercise(processor, options, state, entered, entered_twice, true);
}

TEST_F(CallbackGroups, LifecycleHonorsActivationGate)
{
  if constexpr (!Processor<CallbackLifecycleBase>::activation_gated) {
    GTEST_SKIP() << "The selected lifecycle provider does not have an activation gate";
  }

  auto options = node_options();
  auto state = std::make_shared<WorkState>();
  auto entered = state->entered.get_future();
  auto processor = std::make_shared<Processor<CallbackLifecycleBase>>(options, state);
  auto driver = std::make_shared<rclcpp::Node>("driver", options);
  auto publisher = driver->create_publisher<Work>("work", 10);
  auto client = driver->create_client<Status>("status");
  RunningExecutor running(state);
  running.start(processor, driver);
  ASSERT_TRUE(client->wait_for_service(5s));
  const auto deadline = std::chrono::steady_clock::now() + 5s;
  while (publisher->get_subscription_count() == 0 && std::chrono::steady_clock::now() < deadline) {
    std::this_thread::sleep_for(10ms);
  }
  ASSERT_EQ(publisher->get_subscription_count(), 1u);

  publisher->publish(Work{});
  EXPECT_EQ(entered.wait_for(300ms), std::future_status::timeout);
  auto inactive = client->async_send_request(std::make_shared<Status::Request>());
  EXPECT_EQ(inactive.wait_for(300ms), std::future_status::timeout);
  client->remove_pending_request(inactive.request_id);

  ASSERT_EQ(processor->configure().id(), LifecycleState::PRIMARY_STATE_INACTIVE);
  ASSERT_EQ(processor->activate().id(), LifecycleState::PRIMARY_STATE_ACTIVE);
  publisher->publish(Work{});
  ASSERT_EQ(entered.wait_for(5s), std::future_status::ready);
  auto active = client->async_send_request(std::make_shared<Status::Request>());
  ASSERT_EQ(active.wait_for(3s), std::future_status::ready);
  EXPECT_TRUE(active.get()->success);

  // Deactivation may overlap admitted work; it must not wait for this handler.
  ASSERT_EQ(processor->deactivate().id(), LifecycleState::PRIMARY_STATE_INACTIVE);
  auto deactivated = client->async_send_request(std::make_shared<Status::Request>());
  EXPECT_EQ(deactivated.wait_for(300ms), std::future_status::timeout);
  client->remove_pending_request(deactivated.request_id);
}

}  // namespace
