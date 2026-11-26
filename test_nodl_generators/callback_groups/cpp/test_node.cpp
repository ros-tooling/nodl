// SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
// SPDX-License-Identifier: Apache-2.0
#include <atomic>
#include <chrono>
#include <future>
#include <memory>
#include <mutex>
#include <string>
#include <thread>
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
public:
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
  void check(bool concurrent)
  {
    auto state = std::make_shared<WorkState>();
    auto entered = state->entered.get_future();
    auto options = node_options();
    auto processor = std::make_shared<Processor<Base>>(options, state);
    exercise(processor, options, state, entered, concurrent);
  }

  template <typename Node>
  void exercise(
    const std::shared_ptr<Node> & processor,
    const rclcpp::NodeOptions & options,
    const std::shared_ptr<WorkState> & state,
    std::future<void> & entered,
    bool concurrent)
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

    auto response = client->async_send_request(std::make_shared<Status::Request>());
    const auto ready = response.wait_for(concurrent ? 3s : 300ms);
    EXPECT_EQ(ready == std::future_status::ready, concurrent);
    state->release_work();
    ASSERT_EQ(response.wait_for(3s), std::future_status::ready);
    EXPECT_TRUE(response.get()->success);
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

// Inspect actual endpoint registration, independently of executor timing.
template <typename Node>
rclcpp::CallbackGroup::SharedPtr work_group(const std::shared_ptr<Node> & node)
{
  rclcpp::CallbackGroup::SharedPtr result;
  node->get_node_base_interface()->for_each_callback_group([&result](rclcpp::CallbackGroup::SharedPtr group) {
    if (group->find_subscription_ptrs_if([](const auto & subscription) {
          const std::string topic = subscription->get_topic_name();
          return topic.size() >= 5 && topic.compare(topic.size() - 5, 5, "/work") == 0;
        }))
    {
      result = group;
    }
  });
  return result;
}

TEST_F(CallbackGroups, ReentrantGroupAllowsDistinctEndpointsToOverlap)
{
  auto options = node_options();
  auto state = std::make_shared<WorkState>();
  auto entered = state->entered.get_future();
  auto processor = std::make_shared<Processor<CallbackReentrantBase>>(options, state);
  const auto group = work_group(processor);
  ASSERT_NE(group, nullptr);
  EXPECT_EQ(group->type(), rclcpp::CallbackGroupType::Reentrant);
  EXPECT_NE(group, processor->get_node_base_interface()->get_default_callback_group());
  const auto status_name = std::string(processor->get_namespace()) + "/status";
  ASSERT_NE(
    group->find_service_ptrs_if(
      [&status_name](const auto & service) { return service->get_service_name() == status_name; }),
    nullptr);
  exercise(processor, options, state, entered, true);
}

TEST_F(CallbackGroups, ManagedEndpointsReuseTheirConfiguredGroups)
{
  auto processor = std::make_shared<Processor<CallbackLifecycleBase>>(node_options(), std::make_shared<WorkState>());
  const auto status_name = std::string(processor->get_namespace()) + "/status";
  const auto status_group = [&] {
    rclcpp::CallbackGroup::SharedPtr result;
    processor->get_node_base_interface()->for_each_callback_group([&](rclcpp::CallbackGroup::SharedPtr group) {
      if (group->find_service_ptrs_if([&](const auto & service) { return service->get_service_name() == status_name; }))
      {
        result = group;
      }
    });
    return result;
  };
  ASSERT_EQ(processor->configure().id(), LifecycleState::PRIMARY_STATE_INACTIVE);
  EXPECT_EQ(work_group(processor), nullptr);
  EXPECT_EQ(status_group(), nullptr);
  ASSERT_EQ(processor->activate().id(), LifecycleState::PRIMARY_STATE_ACTIVE);
  const auto work = work_group(processor);
  const auto status = status_group();
  ASSERT_NE(work, nullptr);
  ASSERT_NE(status, nullptr);
  const auto default_group = processor->get_node_base_interface()->get_default_callback_group();
  EXPECT_NE(work, default_group);
  EXPECT_NE(status, default_group);
  EXPECT_NE(work, status);
  EXPECT_EQ(work->type(), rclcpp::CallbackGroupType::MutuallyExclusive);
  EXPECT_EQ(status->type(), rclcpp::CallbackGroupType::MutuallyExclusive);
  ASSERT_EQ(processor->deactivate().id(), LifecycleState::PRIMARY_STATE_INACTIVE);
  EXPECT_EQ(work_group(processor), nullptr);
  EXPECT_EQ(status_group(), nullptr);
  ASSERT_EQ(processor->activate().id(), LifecycleState::PRIMARY_STATE_ACTIVE);
  EXPECT_EQ(work_group(processor), work);
  EXPECT_EQ(status_group(), status);
}

TEST_F(CallbackGroups, LifecycleKeepsGroupsAcrossTransitions)
{
  auto options = node_options();
  auto state = std::make_shared<WorkState>();
  auto entered = state->entered.get_future();
  auto processor = std::make_shared<Processor<CallbackLifecycleBase>>(options, state);
  ASSERT_EQ(processor->configure().id(), LifecycleState::PRIMARY_STATE_INACTIVE);
  ASSERT_EQ(processor->activate().id(), LifecycleState::PRIMARY_STATE_ACTIVE);
  ASSERT_EQ(processor->deactivate().id(), LifecycleState::PRIMARY_STATE_INACTIVE);
  ASSERT_EQ(processor->cleanup().id(), LifecycleState::PRIMARY_STATE_UNCONFIGURED);
  ASSERT_EQ(processor->configure().id(), LifecycleState::PRIMARY_STATE_INACTIVE);
  ASSERT_EQ(processor->activate().id(), LifecycleState::PRIMARY_STATE_ACTIVE);
  exercise(processor, options, state, entered, true);
}

}  // namespace
