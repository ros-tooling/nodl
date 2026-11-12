// SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
// SPDX-License-Identifier: Apache-2.0
#include <gtest/gtest.h>

#include <atomic>
#include <chrono>
#include <future>
#include <map>
#include <memory>
#include <stdexcept>
#include <string>
#include <thread>
#include <utility>
#include <vector>

#include "lifecycle_msgs/msg/state.hpp"
#include "lifecycle_msgs/msg/transition.hpp"
#include "lifecycle_msgs/srv/change_state.hpp"
#include "nodl_runtime_cpp/lifecycle_node.hpp"
#include "rclcpp/rclcpp.hpp"
#include "std_msgs/msg/string.hpp"

namespace
{

using CallbackReturn = nodl_runtime_cpp::LifecycleNode::CallbackReturn;
using lifecycle_msgs::msg::State;

/// How one hook ends.
enum class Outcome
{
  SUCCESS,
  FAILURE,
  THROW,
};

/// A hand-written node that holds a lifecycle publisher and records its hook calls.
class RecordingNode : public nodl_runtime_cpp::LifecycleNode
{
public:
  RecordingNode()
  : nodl_runtime_cpp::LifecycleNode("recording_node")
  , publisher_(create_publisher<std_msgs::msg::String>("chatter", 10))
  {}

  /// The hooks called so far, in order.
  std::vector<std::string> calls;
  /// Whether the publisher was active when each hook was called.
  std::vector<bool> publisher_active_in_hook;
  Outcome activate_outcome = Outcome::SUCCESS;
  Outcome deactivate_outcome = Outcome::SUCCESS;

  bool publisher_active() const
  {
    return publisher_->is_activated();
  }

  uint8_t state_id()
  {
    return get_current_state().id();
  }

protected:
  CallbackReturn handle_configure(const rclcpp_lifecycle::State &) override
  {
    return record("configure", Outcome::SUCCESS);
  }

  CallbackReturn handle_activate(const rclcpp_lifecycle::State &) override
  {
    return record("activate", activate_outcome);
  }

  CallbackReturn handle_deactivate(const rclcpp_lifecycle::State &) override
  {
    return record("deactivate", deactivate_outcome);
  }

  CallbackReturn handle_cleanup(const rclcpp_lifecycle::State &) override
  {
    return record("cleanup", Outcome::SUCCESS);
  }

  CallbackReturn handle_shutdown(const rclcpp_lifecycle::State &) override
  {
    return record("shutdown", Outcome::SUCCESS);
  }

  CallbackReturn handle_error(const rclcpp_lifecycle::State &) override
  {
    return record("error", Outcome::SUCCESS);
  }

private:
  CallbackReturn record(const std::string & name, Outcome outcome)
  {
    calls.push_back(name);
    publisher_active_in_hook.push_back(publisher_->is_activated());
    switch (outcome) {
      case Outcome::FAILURE:
        return CallbackReturn::FAILURE;
      case Outcome::THROW:
        throw std::runtime_error("hook failed");
      case Outcome::SUCCESS:
        break;
    }
    return CallbackReturn::SUCCESS;
  }

  rclcpp_lifecycle::LifecyclePublisher<std_msgs::msg::String>::SharedPtr publisher_;
};

class LifecycleNodeTest : public ::testing::Test
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

  std::shared_ptr<RecordingNode> node_ = std::make_shared<RecordingNode>();
};

TEST_F(LifecycleNodeTest, DefaultHooksSucceed)
{
  auto node = std::make_shared<nodl_runtime_cpp::LifecycleNode>("plain_node");

  EXPECT_EQ(node->configure().id(), State::PRIMARY_STATE_INACTIVE);
  EXPECT_EQ(node->activate().id(), State::PRIMARY_STATE_ACTIVE);
  EXPECT_EQ(node->deactivate().id(), State::PRIMARY_STATE_INACTIVE);
  EXPECT_EQ(node->cleanup().id(), State::PRIMARY_STATE_UNCONFIGURED);
  EXPECT_EQ(node->shutdown().id(), State::PRIMARY_STATE_FINALIZED);
}

TEST_F(LifecycleNodeTest, EachHookRunsOncePerTransitionInOrder)
{
  node_->configure();
  node_->activate();
  node_->deactivate();
  node_->cleanup();
  node_->shutdown();

  EXPECT_EQ(node_->calls, (std::vector<std::string>{"configure", "activate", "deactivate", "cleanup", "shutdown"}));
}

TEST_F(LifecycleNodeTest, PublisherIsActiveDuringActivateAndAfter)
{
  node_->configure();
  EXPECT_FALSE(node_->publisher_active());

  node_->activate();

  EXPECT_EQ(node_->state_id(), State::PRIMARY_STATE_ACTIVE);
  EXPECT_TRUE(node_->publisher_active());
  // configure, activate
  EXPECT_EQ(node_->publisher_active_in_hook, (std::vector<bool>{false, true}));
}

TEST_F(LifecycleNodeTest, DeactivateRunsHookBeforePublisherDeactivates)
{
  node_->configure();
  node_->activate();

  node_->deactivate();

  EXPECT_EQ(node_->state_id(), State::PRIMARY_STATE_INACTIVE);
  EXPECT_FALSE(node_->publisher_active());
  // configure, activate, deactivate
  EXPECT_EQ(node_->publisher_active_in_hook, (std::vector<bool>{false, true, true}));
}

TEST_F(LifecycleNodeTest, FailingActivateLeavesNodeAndPublisherInactive)
{
  node_->activate_outcome = Outcome::FAILURE;
  node_->configure();

  node_->activate();

  EXPECT_EQ(node_->state_id(), State::PRIMARY_STATE_INACTIVE);
  EXPECT_FALSE(node_->publisher_active());
  EXPECT_EQ(node_->calls, (std::vector<std::string>{"configure", "activate"}));
}

TEST_F(LifecycleNodeTest, ThrowingActivateRunsErrorAndLeavesPublisherInactive)
{
  node_->activate_outcome = Outcome::THROW;
  node_->configure();

  node_->activate();

  EXPECT_EQ(node_->state_id(), State::PRIMARY_STATE_UNCONFIGURED);
  EXPECT_FALSE(node_->publisher_active());
  EXPECT_EQ(node_->calls, (std::vector<std::string>{"configure", "activate", "error"}));
}

TEST_F(LifecycleNodeTest, ShutdownFromActiveDeactivatesPublisherBeforeHook)
{
  node_->configure();
  node_->activate();

  node_->shutdown();

  EXPECT_EQ(node_->state_id(), State::PRIMARY_STATE_FINALIZED);
  EXPECT_FALSE(node_->publisher_active());
  // configure, activate, deactivate, shutdown
  EXPECT_EQ(node_->calls, (std::vector<std::string>{"configure", "activate", "deactivate", "shutdown"}));
  EXPECT_EQ(node_->publisher_active_in_hook, (std::vector<bool>{false, true, true, false}));
}

TEST_F(LifecycleNodeTest, ErrorDeactivatesPublisherBeforeHook)
{
  node_->deactivate_outcome = Outcome::THROW;
  node_->configure();
  node_->activate();

  node_->deactivate();

  EXPECT_EQ(node_->state_id(), State::PRIMARY_STATE_UNCONFIGURED);
  EXPECT_FALSE(node_->publisher_active());
  EXPECT_EQ(node_->calls, (std::vector<std::string>{"configure", "activate", "deactivate", "error"}));
  // configure, activate, deactivate, error
  EXPECT_EQ(node_->publisher_active_in_hook, (std::vector<bool>{false, true, true, false}));
}

TEST_F(LifecycleNodeTest, FailingDeactivateKeepsNodeAndPublisherActive)
{
  node_->deactivate_outcome = Outcome::FAILURE;
  node_->configure();
  node_->activate();

  node_->deactivate();

  EXPECT_EQ(node_->state_id(), State::PRIMARY_STATE_ACTIVE);
  EXPECT_TRUE(node_->publisher_active());
}

/// A hand-written node whose slots and hooks all record into one event log.
class SlotNode : public nodl_runtime_cpp::LifecycleNode
{
public:
  explicit SlotNode(std::shared_ptr<std::vector<std::string>> log = std::make_shared<std::vector<std::string>>())
  : nodl_runtime_cpp::LifecycleNode("slot_node")
  , log(std::move(log))
  {}

  using nodl_runtime_cpp::LifecycleNode::add_activation_slot;
  using nodl_runtime_cpp::LifecycleNode::manage;

  /// Registers a slot that logs `create <name>` and `destroy <name>`, and throws from `create` when asked to.
  void add_logging_slot(const std::string & name, bool throw_on_create = false)
  {
    add_activation_slot(
      [this, name, throw_on_create] {
        if (throw_on_create) {
          throw std::runtime_error("create failed");
        }
        log->push_back("create " + name);
      },
      [this, name] { log->push_back("destroy " + name); });
  }

  uint8_t state_id()
  {
    return get_current_state().id();
  }

  /// Registers a slot while a hook runs, to show that late registration throws.
  bool register_in_activate = false;
  bool late_registration_threw = false;
  /// What each hook returns or does, by hook name without the `handle_` prefix.
  std::map<std::string, Outcome> outcomes;
  std::shared_ptr<std::vector<std::string>> log;

protected:
  CallbackReturn handle_configure(const rclcpp_lifecycle::State &) override
  {
    return record("configure");
  }

  CallbackReturn handle_activate(const rclcpp_lifecycle::State &) override
  {
    if (register_in_activate) {
      try {
        add_logging_slot("late");
      } catch (const std::logic_error &) {
        late_registration_threw = true;
      }
    }
    return record("activate");
  }

  CallbackReturn handle_deactivate(const rclcpp_lifecycle::State &) override
  {
    return record("deactivate");
  }

  CallbackReturn handle_cleanup(const rclcpp_lifecycle::State &) override
  {
    return record("cleanup");
  }

  CallbackReturn handle_shutdown(const rclcpp_lifecycle::State &) override
  {
    return record("shutdown");
  }

  CallbackReturn handle_error(const rclcpp_lifecycle::State &) override
  {
    return record("error");
  }

private:
  CallbackReturn record(const std::string & name)
  {
    log->push_back("hook " + name);
    switch (outcomes.count(name) ? outcomes.at(name) : Outcome::SUCCESS) {
      case Outcome::FAILURE:
        return CallbackReturn::FAILURE;
      case Outcome::THROW:
        throw std::runtime_error("hook failed");
      case Outcome::SUCCESS:
        break;
    }
    return CallbackReturn::SUCCESS;
  }
};

using Log = std::vector<std::string>;

class ActivationRegistry : public ::testing::Test
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
    node_->add_logging_slot("a");
    node_->add_logging_slot("b");
    node_->add_logging_slot("c");
  }

  std::shared_ptr<SlotNode> node_ = std::make_shared<SlotNode>();
};

TEST_F(ActivationRegistry, SlotsAreCreatedInOrderBeforeTheHook)
{
  node_->configure();
  node_->log->clear();

  EXPECT_EQ(node_->activate().id(), State::PRIMARY_STATE_ACTIVE);

  EXPECT_EQ(*node_->log, (Log{"create a", "create b", "create c", "hook activate"}));
}

TEST_F(ActivationRegistry, SlotsAreDestroyedInReverseAfterTheHook)
{
  node_->configure();
  node_->activate();
  node_->log->clear();

  EXPECT_EQ(node_->deactivate().id(), State::PRIMARY_STATE_INACTIVE);

  EXPECT_EQ(*node_->log, (Log{"hook deactivate", "destroy c", "destroy b", "destroy a"}));
}

TEST_F(ActivationRegistry, ConfigureAndCleanupRunOnlyTheHooks)
{
  node_->configure();
  node_->cleanup();

  EXPECT_EQ(*node_->log, (Log{"hook configure", "hook cleanup"}));
}

TEST_F(ActivationRegistry, RepeatedCyclesCreateAndDestroyEverySlotEveryTime)
{
  node_->configure();
  for (int cycle = 0; cycle < 3; ++cycle) {
    EXPECT_EQ(node_->activate().id(), State::PRIMARY_STATE_ACTIVE);
    EXPECT_EQ(node_->deactivate().id(), State::PRIMARY_STATE_INACTIVE);
  }

  const Log cycle{
    "create a", "create b", "create c", "hook activate", "hook deactivate", "destroy c", "destroy b", "destroy a"};
  Log expected{"hook configure"};
  for (int i = 0; i < 3; ++i) {
    expected.insert(expected.end(), cycle.begin(), cycle.end());
  }
  EXPECT_EQ(*node_->log, expected);
}

TEST_F(ActivationRegistry, ThrowingCreatorRollsBackTheCreatedSlotsAndRunsError)
{
  node_->add_logging_slot("d", true);
  node_->add_logging_slot("e");
  node_->configure();
  node_->log->clear();

  node_->activate();

  EXPECT_EQ(
    *node_->log, (Log{"create a", "create b", "create c", "destroy c", "destroy b", "destroy a", "hook error"}));
  EXPECT_EQ(node_->state_id(), State::PRIMARY_STATE_UNCONFIGURED);
}

TEST_F(ActivationRegistry, FailingActivateHookDestroysTheSlots)
{
  node_->outcomes["activate"] = Outcome::FAILURE;
  node_->configure();
  node_->log->clear();

  EXPECT_EQ(node_->activate().id(), State::PRIMARY_STATE_INACTIVE);

  EXPECT_EQ(
    *node_->log, (Log{"create a", "create b", "create c", "hook activate", "destroy c", "destroy b", "destroy a"}));
}

TEST_F(ActivationRegistry, ThrowingActivateHookDestroysTheSlotsBeforeTheErrorHook)
{
  node_->outcomes["activate"] = Outcome::THROW;
  node_->configure();
  node_->log->clear();

  node_->activate();

  EXPECT_EQ(
    *node_->log,
    (Log{"create a", "create b", "create c", "hook activate", "destroy c", "destroy b", "destroy a", "hook error"}));
  EXPECT_EQ(node_->state_id(), State::PRIMARY_STATE_UNCONFIGURED);
}

TEST_F(ActivationRegistry, FailingDeactivateHookKeepsTheSlots)
{
  node_->outcomes["deactivate"] = Outcome::FAILURE;
  node_->configure();
  node_->activate();
  node_->log->clear();

  EXPECT_EQ(node_->deactivate().id(), State::PRIMARY_STATE_ACTIVE);

  EXPECT_EQ(*node_->log, (Log{"hook deactivate"}));
}

TEST_F(ActivationRegistry, ThrowingDeactivateHookDestroysTheSlotsBeforeTheErrorHook)
{
  node_->outcomes["deactivate"] = Outcome::THROW;
  node_->configure();
  node_->activate();
  node_->log->clear();

  node_->deactivate();

  EXPECT_EQ(*node_->log, (Log{"hook deactivate", "destroy c", "destroy b", "destroy a", "hook error"}));
  EXPECT_EQ(node_->state_id(), State::PRIMARY_STATE_UNCONFIGURED);
}

TEST_F(ActivationRegistry, ShutdownFromActiveRunsTheDeactivateHookThenDestroysTheSlotsThenTheShutdownHook)
{
  node_->configure();
  node_->activate();
  node_->log->clear();

  EXPECT_EQ(node_->shutdown().id(), State::PRIMARY_STATE_FINALIZED);

  EXPECT_EQ(*node_->log, (Log{"hook deactivate", "destroy c", "destroy b", "destroy a", "hook shutdown"}));
}

TEST_F(ActivationRegistry, ShutdownFromActiveContinuesWhenTheDeactivateHookFails)
{
  node_->outcomes["deactivate"] = Outcome::FAILURE;
  node_->configure();
  node_->activate();
  node_->log->clear();

  EXPECT_EQ(node_->shutdown().id(), State::PRIMARY_STATE_FINALIZED);

  EXPECT_EQ(*node_->log, (Log{"hook deactivate", "destroy c", "destroy b", "destroy a", "hook shutdown"}));
}

TEST_F(ActivationRegistry, ShutdownFromActiveContinuesWhenTheDeactivateHookThrows)
{
  node_->outcomes["deactivate"] = Outcome::THROW;
  node_->configure();
  node_->activate();
  node_->log->clear();

  EXPECT_EQ(node_->shutdown().id(), State::PRIMARY_STATE_FINALIZED);

  EXPECT_EQ(*node_->log, (Log{"hook deactivate", "destroy c", "destroy b", "destroy a", "hook shutdown"}));
}

TEST_F(ActivationRegistry, ErrorFromActiveDoesNotRunTheDeactivateHookAgainWhenItCausedTheError)
{
  node_->outcomes["deactivate"] = Outcome::THROW;
  node_->configure();
  node_->activate();
  node_->log->clear();

  node_->deactivate();

  EXPECT_EQ(*node_->log, (Log{"hook deactivate", "destroy c", "destroy b", "destroy a", "hook error"}));
}

TEST_F(ActivationRegistry, ShutdownFromInactiveAndUnconfiguredDestroysNothing)
{
  EXPECT_EQ(node_->shutdown().id(), State::PRIMARY_STATE_FINALIZED);
  EXPECT_EQ(*node_->log, (Log{"hook shutdown"}));

  auto inactive = std::make_shared<SlotNode>();
  inactive->add_logging_slot("a");
  inactive->configure();
  inactive->activate();
  inactive->deactivate();
  inactive->log->clear();

  EXPECT_EQ(inactive->shutdown().id(), State::PRIMARY_STATE_FINALIZED);
  EXPECT_EQ(*inactive->log, (Log{"hook shutdown"}));
}

TEST_F(ActivationRegistry, ErrorFromEveryStateDestroysTheSlotsOnlyWhenActive)
{
  // Unconfigured: the configure hook throws.
  node_->outcomes["configure"] = Outcome::THROW;
  node_->configure();
  EXPECT_EQ(*node_->log, (Log{"hook configure", "hook error"}));

  // Inactive: the cleanup hook throws.
  auto inactive = std::make_shared<SlotNode>();
  inactive->add_logging_slot("a");
  inactive->outcomes["cleanup"] = Outcome::THROW;
  inactive->configure();
  inactive->log->clear();
  inactive->cleanup();
  EXPECT_EQ(*inactive->log, (Log{"hook cleanup", "hook error"}));

  // Active: the deactivate hook throws, and the slots are destroyed before the error hook.
  auto active = std::make_shared<SlotNode>();
  active->add_logging_slot("a");
  active->outcomes["deactivate"] = Outcome::THROW;
  active->configure();
  active->activate();
  active->log->clear();
  active->deactivate();
  EXPECT_EQ(*active->log, (Log{"hook deactivate", "destroy a", "hook error"}));
}

TEST_F(ActivationRegistry, RegisteringWhileActiveThrows)
{
  node_->register_in_activate = true;
  node_->configure();

  node_->activate();

  EXPECT_TRUE(node_->late_registration_threw);
  EXPECT_EQ(node_->state_id(), State::PRIMARY_STATE_ACTIVE);
  node_->deactivate();
  // The rejected slot never ran.
  EXPECT_EQ(
    *node_->log,
    (Log{
      "hook configure",
      "create a",
      "create b",
      "create c",
      "hook activate",
      "hook deactivate",
      "destroy c",
      "destroy b",
      "destroy a"}));
}

/// Registers a slot from inside the first `create`, or from `handle_activate` of a node that has no slots.
class LateRegistrationNode : public nodl_runtime_cpp::LifecycleNode
{
public:
  LateRegistrationNode()
  : nodl_runtime_cpp::LifecycleNode("late_registration_node")
  {}

  using nodl_runtime_cpp::LifecycleNode::add_activation_slot;

  bool register_in_activate = false;
  bool threw_in_activate = false;
  bool threw_in_create = false;

protected:
  CallbackReturn handle_activate(const rclcpp_lifecycle::State &) override
  {
    if (register_in_activate) {
      try {
        add_activation_slot([] {}, [] {});
      } catch (const std::logic_error &) {
        threw_in_activate = true;
      }
    }
    return CallbackReturn::SUCCESS;
  }
};

TEST_F(ActivationRegistry, RegisteringFromHandleActivateOfANodeWithoutSlotsThrows)
{
  auto node = std::make_shared<LateRegistrationNode>();
  node->register_in_activate = true;
  node->configure();

  node->activate();

  EXPECT_TRUE(node->threw_in_activate);
}

TEST_F(ActivationRegistry, RegisteringFromInsideTheFirstCreateThrows)
{
  auto node = std::make_shared<LateRegistrationNode>();
  node->add_activation_slot(
    [&node] {
      try {
        node->add_activation_slot([] {}, [] {});
      } catch (const std::logic_error &) {
        node->threw_in_create = true;
      }
    },
    [] {});
  node->configure();

  node->activate();

  EXPECT_TRUE(node->threw_in_create);
}

TEST_F(ActivationRegistry, SlotsCanBeRegisteredAgainAfterDeactivation)
{
  auto node = std::make_shared<LateRegistrationNode>();
  node->configure();
  node->activate();
  node->deactivate();

  EXPECT_NO_THROW(node->add_activation_slot([] {}, [] {}));
}

TEST(ActivationRegistryLifetime, DestroyingAnActiveNodeDoesNotCallDestroy)
{
  rclcpp::init(0, nullptr);
  auto log = std::make_shared<Log>();
  {
    auto node = std::make_shared<SlotNode>(log);
    node->add_logging_slot("a");
    node->configure();
    node->activate();
    log->clear();
  }
  rclcpp::shutdown();

  EXPECT_TRUE(log->empty());
}

/// Owns a member that a slot manages, to check that the member follows the node's activation.
class ManagedNode : public nodl_runtime_cpp::LifecycleNode
{
public:
  ManagedNode()
  : nodl_runtime_cpp::LifecycleNode("managed_node")
  {
    manage(subscription, [this] {
      return create_subscription<std_msgs::msg::String>("chatter", 10, [](std_msgs::msg::String::ConstSharedPtr) {});
    });
  }

  rclcpp::Subscription<std_msgs::msg::String>::SharedPtr subscription;
};

TEST_F(ActivationRegistry, ManagedMemberIsNullUntilActivationAndAfterDeactivation)
{
  auto node = std::make_shared<ManagedNode>();
  EXPECT_EQ(node->subscription, nullptr);

  node->configure();
  EXPECT_EQ(node->subscription, nullptr);

  node->activate();
  ASSERT_NE(node->subscription, nullptr);
  EXPECT_EQ(node->subscription->get_topic_name(), std::string("/chatter"));

  node->deactivate();
  EXPECT_EQ(node->subscription, nullptr);

  node->activate();
  EXPECT_NE(node->subscription, nullptr);
}

template <typename PredicateT>
bool wait_for(PredicateT predicate)
{
  const auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(10);
  while (!predicate() && std::chrono::steady_clock::now() < deadline) {
    std::this_thread::sleep_for(std::chrono::milliseconds(5));
  }
  return predicate();
}

/// Creates a subscription at activation with the given QoS, and counts what it receives.
class SubscriberNode : public nodl_runtime_cpp::LifecycleNode
{
public:
  explicit SubscriberNode(const rclcpp::QoS & qos)
  : nodl_runtime_cpp::LifecycleNode("subscriber_node")
  {
    manage(subscription, [this, qos] {
      return create_subscription<std_msgs::msg::String>(
        "in", qos, [this](std_msgs::msg::String::ConstSharedPtr) { ++received; });
    });
  }

  rclcpp::Subscription<std_msgs::msg::String>::SharedPtr subscription;
  std::atomic<int> received{0};
};

/// Counts the ticks of a timer that it creates in `handle_activate` and resets in `handle_deactivate`.
class TimerNode : public nodl_runtime_cpp::LifecycleNode
{
public:
  TimerNode()
  : nodl_runtime_cpp::LifecycleNode("timer_node")
  {
    manage(subscription, [this] {
      return create_subscription<std_msgs::msg::String>("in", 10, [](std_msgs::msg::String::ConstSharedPtr) {});
    });
  }

  rclcpp::Subscription<std_msgs::msg::String>::SharedPtr subscription;
  std::atomic<int> ticks{0};
  /// Ticks that found the subscription null.
  std::atomic<int> ticks_without_subscription{0};

protected:
  CallbackReturn handle_activate(const rclcpp_lifecycle::State &) override
  {
    timer_ = create_wall_timer(std::chrono::milliseconds(5), [this] {
      ++ticks;
      if (nullptr == subscription) {
        ++ticks_without_subscription;
      }
    });
    return CallbackReturn::SUCCESS;
  }

  CallbackReturn handle_deactivate(const rclcpp_lifecycle::State &) override
  {
    timer_.reset();
    return CallbackReturn::SUCCESS;
  }

private:
  rclcpp::TimerBase::SharedPtr timer_;
};

using lifecycle_msgs::msg::Transition;

/// Requests transitions of a node through its lifecycle services, which an executor serializes with the node's callbacks.
class ActivationRegistryServices : public ::testing::Test
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

  template <typename NodeT>
  void start(const std::shared_ptr<NodeT> & node)
  {
    client_ =
      peer_->create_client<lifecycle_msgs::srv::ChangeState>(std::string("/") + node->get_name() + "/change_state");
    node_ = node;
    executor_.add_node(node->get_node_base_interface());
    executor_.add_node(peer_);
    spinner_ = std::thread([this] { executor_.spin(); });
    ASSERT_TRUE(client_->wait_for_service(std::chrono::seconds(10)));
  }

  void TearDown() override
  {
    executor_.cancel();
    if (spinner_.joinable()) {
      spinner_.join();
    }
  }

  /// Requests a transition and returns whether it succeeded.
  bool change_state(uint8_t transition_id)
  {
    auto request = std::make_shared<lifecycle_msgs::srv::ChangeState::Request>();
    request->transition.id = transition_id;
    auto response = client_->async_send_request(request);
    return std::future_status::ready == response.future.wait_for(std::chrono::seconds(10)) &&
           response.future.get()->success;
  }

  /// The node outlives the spinning executor, which `TearDown` stops.
  std::shared_ptr<rclcpp_lifecycle::LifecycleNode> node_;
  std::shared_ptr<rclcpp::Node> peer_ = std::make_shared<rclcpp::Node>("peer_node");
  rclcpp::Client<lifecycle_msgs::srv::ChangeState>::SharedPtr client_;
  rclcpp::executors::MultiThreadedExecutor executor_{rclcpp::ExecutorOptions(), 4};
  std::thread spinner_;
};

TEST_F(ActivationRegistryServices, SubscriptionReceivesOnlyWhileActive)
{
  auto node = std::make_shared<SubscriberNode>(rclcpp::QoS(10));
  auto in = peer_->create_publisher<std_msgs::msg::String>("in", 10);
  start(node);
  ASSERT_TRUE(change_state(Transition::TRANSITION_CONFIGURE));
  // The node has no subscription yet, so nothing is delivered.
  EXPECT_EQ(0u, in->get_subscription_count());
  in->publish(std_msgs::msg::String());

  ASSERT_TRUE(change_state(Transition::TRANSITION_ACTIVATE));
  ASSERT_TRUE(wait_for([&] { return 1u == in->get_subscription_count(); }));
  std::this_thread::sleep_for(std::chrono::milliseconds(300));
  EXPECT_EQ(0, node->received);
  in->publish(std_msgs::msg::String());
  EXPECT_TRUE(wait_for([&] { return 1 == node->received; }));

  ASSERT_TRUE(change_state(Transition::TRANSITION_DEACTIVATE));
  EXPECT_TRUE(wait_for([&] { return 0u == in->get_subscription_count(); }));
  in->publish(std_msgs::msg::String());
  std::this_thread::sleep_for(std::chrono::milliseconds(300));
  EXPECT_EQ(1, node->received);
}

TEST_F(ActivationRegistryServices, TransientLocalSubscriptionGetsTheLatchedMessageOnlyAfterActivation)
{
  auto node = std::make_shared<SubscriberNode>(rclcpp::QoS(10).transient_local());
  auto in = peer_->create_publisher<std_msgs::msg::String>("in", rclcpp::QoS(10).transient_local());
  in->publish(std_msgs::msg::String());
  start(node);
  ASSERT_TRUE(change_state(Transition::TRANSITION_CONFIGURE));
  std::this_thread::sleep_for(std::chrono::milliseconds(300));
  EXPECT_EQ(0, node->received);

  ASSERT_TRUE(change_state(Transition::TRANSITION_ACTIVATE));
  EXPECT_TRUE(wait_for([&] { return 1 == node->received; }));

  // Deactivating and activating again creates a new subscription, which gets the latched message again.
  ASSERT_TRUE(change_state(Transition::TRANSITION_DEACTIVATE));
  ASSERT_TRUE(change_state(Transition::TRANSITION_ACTIVATE));
  EXPECT_TRUE(wait_for([&] { return 2 == node->received; }));
}

TEST(ActivationRegistryExecutor, DeactivatingAfterASubscriptionRanWhileAnExecutorIsIdleDestroysIt)
{
  rclcpp::init(0, nullptr);
  {
    auto node = std::make_shared<SubscriberNode>(rclcpp::QoS(10));
    auto peer = std::make_shared<rclcpp::Node>("peer_node");
    auto in = peer->create_publisher<std_msgs::msg::String>("in", 10);
    rclcpp::executors::MultiThreadedExecutor executor(rclcpp::ExecutorOptions(), 4);
    executor.add_node(node->get_node_base_interface());
    executor.add_node(peer);
    std::thread spinner([&executor] { executor.spin(); });
    node->configure();
    node->activate();
    ASSERT_TRUE(wait_for([&] { return 1u == in->get_subscription_count(); }));
    in->publish(std_msgs::msg::String());
    ASSERT_TRUE(wait_for([&] { return 1 == node->received; }));

    // An idle executor thread still holds the subscription it executed last, until something wakes it.
    node->deactivate();

    EXPECT_TRUE(wait_for([&] { return 0u == in->get_subscription_count(); }));
    executor.cancel();
    spinner.join();
  }
  rclcpp::shutdown();
}

TEST_F(ActivationRegistryServices, TimerCreatedInTheActivateHookNeverSeesANullSubscription)
{
  auto node = std::make_shared<TimerNode>();
  start(node);
  ASSERT_TRUE(change_state(Transition::TRANSITION_CONFIGURE));
  EXPECT_EQ(0, node->ticks);
  ASSERT_TRUE(change_state(Transition::TRANSITION_ACTIVATE));
  ASSERT_TRUE(wait_for([&] { return 0 != node->ticks; }));

  ASSERT_TRUE(change_state(Transition::TRANSITION_ACTIVE_SHUTDOWN));

  const auto ticks = node->ticks.load();
  std::this_thread::sleep_for(std::chrono::milliseconds(200));
  EXPECT_EQ(ticks, node->ticks);
  EXPECT_EQ(0, node->ticks_without_subscription);
  EXPECT_EQ(nullptr, node->subscription);
}

TEST_F(ActivationRegistryServices, CyclingUnderLoadWithAMultiThreadedExecutor)
{
  auto node = std::make_shared<SubscriberNode>(rclcpp::QoS(10));
  auto in = peer_->create_publisher<std_msgs::msg::String>("in", 10);
  start(node);
  std::atomic<bool> stop{false};
  std::thread load([&] {
    while (!stop) {
      in->publish(std_msgs::msg::String());
      std::this_thread::sleep_for(std::chrono::milliseconds(1));
    }
  });

  ASSERT_TRUE(change_state(Transition::TRANSITION_CONFIGURE));
  for (int cycle = 0; cycle < 30; ++cycle) {
    ASSERT_TRUE(change_state(Transition::TRANSITION_ACTIVATE));
    std::this_thread::sleep_for(std::chrono::milliseconds(30));
    ASSERT_TRUE(change_state(Transition::TRANSITION_DEACTIVATE));
  }
  ASSERT_TRUE(change_state(Transition::TRANSITION_ACTIVATE));
  const auto before = node->received.load();
  EXPECT_TRUE(wait_for([&] { return before != node->received; }));

  stop = true;
  load.join();
}

}  // namespace
