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
#include "nodl_runtime_cpp/lifecycle_node.hpp"
#include "rclcpp/create_publisher.hpp"
#include "rclcpp/rclcpp.hpp"
#include "std_msgs/msg/string.hpp"
#include "std_srvs/srv/set_bool.hpp"

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
  // configure, activate, shutdown
  EXPECT_EQ(node_->publisher_active_in_hook, (std::vector<bool>{false, true, false}));
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

TEST_F(ActivationRegistry, ShutdownFromActiveDestroysTheSlotsBeforeTheHook)
{
  node_->configure();
  node_->activate();
  node_->log->clear();

  EXPECT_EQ(node_->shutdown().id(), State::PRIMARY_STATE_FINALIZED);

  EXPECT_EQ(*node_->log, (Log{"destroy c", "destroy b", "destroy a", "hook shutdown"}));
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
    manage(
      publisher, [this] { return rclcpp::create_publisher<std_msgs::msg::String>(*this, "chatter", rclcpp::QoS(10)); });
  }

  rclcpp::Publisher<std_msgs::msg::String>::SharedPtr publisher;
};

TEST_F(ActivationRegistry, ManagedMemberIsNullUntilActivationAndAfterDeactivation)
{
  auto node = std::make_shared<ManagedNode>();
  EXPECT_EQ(node->publisher, nullptr);

  node->configure();
  EXPECT_EQ(node->publisher, nullptr);

  node->activate();
  ASSERT_NE(node->publisher, nullptr);
  EXPECT_EQ(node->publisher->get_topic_name(), std::string("/chatter"));

  node->deactivate();
  EXPECT_EQ(node->publisher, nullptr);

  node->activate();
  EXPECT_NE(node->publisher, nullptr);
}

/// Owns a service that a slot manages.
class ServiceNode : public nodl_runtime_cpp::LifecycleNode
{
public:
  ServiceNode()
  : nodl_runtime_cpp::LifecycleNode("service_node")
  {
    manage(service, [this] {
      return create_service<std_srvs::srv::SetBool>(
        "set_bool", [](std_srvs::srv::SetBool::Request::SharedPtr, std_srvs::srv::SetBool::Response::SharedPtr) {});
    });
  }

  rclcpp::Service<std_srvs::srv::SetBool>::SharedPtr service;
};

TEST(ActivationRegistryExecutor, DeactivatingAfterAnEndpointRanWhileAnExecutorIsIdleDestroysIt)
{
  rclcpp::init(0, nullptr);
  {
    auto node = std::make_shared<ServiceNode>();
    auto peer = std::make_shared<rclcpp::Node>("peer_node");
    auto client = peer->create_client<std_srvs::srv::SetBool>("set_bool");
    rclcpp::executors::MultiThreadedExecutor executor(rclcpp::ExecutorOptions(), 4);
    executor.add_node(node->get_node_base_interface());
    executor.add_node(peer);
    std::thread spinner([&executor] { executor.spin(); });
    // Polling for the unavailable service first makes the idle executor keep the endpoint it ran last.
    EXPECT_FALSE(client->wait_for_service(std::chrono::milliseconds(500)));
    node->configure();
    EXPECT_FALSE(client->wait_for_service(std::chrono::milliseconds(500)));
    node->activate();
    ASSERT_TRUE(client->wait_for_service(std::chrono::seconds(10)));
    auto response = client->async_send_request(std::make_shared<std_srvs::srv::SetBool::Request>());
    ASSERT_EQ(std::future_status::ready, response.future.wait_for(std::chrono::seconds(10)));

    // An idle executor thread still holds the service it executed last, until something wakes it.
    node->deactivate();

    const auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(10);
    while (client->service_is_ready() && std::chrono::steady_clock::now() < deadline) {
      std::this_thread::sleep_for(std::chrono::milliseconds(10));
    }
    EXPECT_FALSE(client->service_is_ready());
    executor.cancel();
    spinner.join();
  }
  rclcpp::shutdown();
}

/// Owns a client that a slot manages.
class ClientNode : public nodl_runtime_cpp::LifecycleNode
{
public:
  ClientNode()
  : nodl_runtime_cpp::LifecycleNode("client_node")
  {
    manage(client, [this] { return create_client<std_srvs::srv::SetBool>("set_bool"); });
  }

  rclcpp::Client<std_srvs::srv::SetBool>::SharedPtr client;
};

TEST(ActivationRegistryClient, PendingRequestFailsWhenTheNodeDeactivates)
{
  rclcpp::init(0, nullptr);
  {
    auto node = std::make_shared<ClientNode>();
    node->configure();
    node->activate();
    // No service answers, so the request stays pending.
    auto pending = node->client->async_send_request(std::make_shared<std_srvs::srv::SetBool::Request>());
    ASSERT_EQ(std::future_status::timeout, pending.future.wait_for(std::chrono::milliseconds(100)));

    node->deactivate();

    EXPECT_THROW(pending.future.get(), std::future_error);
  }
  rclcpp::shutdown();
}

}  // namespace
