// SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
// SPDX-License-Identifier: Apache-2.0
#include <gtest/gtest.h>

#include <memory>
#include <stdexcept>
#include <string>
#include <vector>

#include "lifecycle_msgs/msg/state.hpp"
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

  /// The parameter seams and the hooks called so far, in order.
  std::vector<std::string> calls;
  /// Whether the publisher was active when each hook was called.
  std::vector<bool> publisher_active_in_hook;
  /// Whether the gate was open when each hook was called.
  std::vector<bool> gate_open_in_hook;
  Outcome activate_outcome = Outcome::SUCCESS;
  Outcome deactivate_outcome = Outcome::SUCCESS;

  bool publisher_active() const
  {
    return publisher_->is_activated();
  }

  bool gate_open() const
  {
    return gate()->is_activated();
  }

  uint8_t state_id()
  {
    return get_current_state().id();
  }

protected:
  void refresh_parameters() override
  {
    calls.push_back("refresh");
  }

  void start_parameter_updates() override
  {
    calls.push_back("start");
  }

  void stop_parameter_updates() override
  {
    calls.push_back("stop");
  }

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
    gate_open_in_hook.push_back(gate()->is_activated());
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

TEST_F(LifecycleNodeTest, ConstructsWithNameAndOptions)
{
  nodl_runtime_cpp::LifecycleNode node("named_node", rclcpp::NodeOptions().use_intra_process_comms(true));

  EXPECT_STREQ(node.get_name(), "named_node");
  EXPECT_STREQ(node.get_namespace(), "/");
  EXPECT_TRUE(node.get_node_options().use_intra_process_comms());
}

TEST_F(LifecycleNodeTest, ConstructsWithNamespaceAndOptions)
{
  nodl_runtime_cpp::LifecycleNode node("named_node", "ns");
  nodl_runtime_cpp::LifecycleNode with_options("other_node", "ns", rclcpp::NodeOptions());

  EXPECT_STREQ(node.get_name(), "named_node");
  EXPECT_STREQ(node.get_namespace(), "/ns");
  EXPECT_STREQ(with_options.get_namespace(), "/ns");
}

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

  EXPECT_EQ(
    node_->calls,
    (std::vector<std::string>{
      "refresh", "configure", "start", "refresh", "activate", "deactivate", "stop", "cleanup", "stop", "shutdown"}));
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

TEST_F(LifecycleNodeTest, GateIsOpenDuringActivateAndClosedOtherwise)
{
  EXPECT_FALSE(node_->gate_open());
  node_->configure();
  EXPECT_FALSE(node_->gate_open());

  node_->activate();
  EXPECT_TRUE(node_->gate_open());

  node_->deactivate();
  EXPECT_FALSE(node_->gate_open());
  // configure, activate, deactivate
  EXPECT_EQ(node_->gate_open_in_hook, (std::vector<bool>{false, true, true}));
}

TEST_F(LifecycleNodeTest, GateClosesWhenActivateFails)
{
  node_->activate_outcome = Outcome::FAILURE;
  node_->configure();

  node_->activate();

  EXPECT_FALSE(node_->gate_open());
  // configure, activate
  EXPECT_EQ(node_->gate_open_in_hook, (std::vector<bool>{false, true}));
}

TEST_F(LifecycleNodeTest, GateClosesOnShutdownFromActive)
{
  node_->configure();
  node_->activate();

  node_->shutdown();

  EXPECT_FALSE(node_->gate_open());
  // configure, activate, shutdown
  EXPECT_EQ(node_->gate_open_in_hook, (std::vector<bool>{false, true, false}));
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
  EXPECT_EQ(node_->calls, (std::vector<std::string>{"refresh", "configure", "start", "refresh", "activate", "stop"}));
}

TEST_F(LifecycleNodeTest, ThrowingActivateRunsErrorAndLeavesPublisherInactive)
{
  node_->activate_outcome = Outcome::THROW;
  node_->configure();

  node_->activate();

  EXPECT_EQ(node_->state_id(), State::PRIMARY_STATE_UNCONFIGURED);
  EXPECT_FALSE(node_->publisher_active());
  EXPECT_EQ(
    node_->calls, (std::vector<std::string>{"refresh", "configure", "start", "refresh", "activate", "stop", "error"}));
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
  EXPECT_EQ(
    node_->calls,
    (std::vector<std::string>{"refresh", "configure", "start", "refresh", "activate", "deactivate", "stop", "error"}));
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

using Sequence = std::vector<std::string>;

TEST_F(LifecycleNodeTest, ParameterSeamsRunInTransitionOrder)
{
  node_->configure();
  EXPECT_EQ(node_->calls, (Sequence{"refresh", "configure"}));

  node_->calls.clear();
  node_->activate();
  EXPECT_EQ(node_->calls, (Sequence{"start", "refresh", "activate"}));

  node_->calls.clear();
  node_->deactivate();
  EXPECT_EQ(node_->calls, (Sequence{"deactivate", "stop"}));

  node_->calls.clear();
  node_->cleanup();
  EXPECT_EQ(node_->calls, (Sequence{"cleanup"}));
}

TEST_F(LifecycleNodeTest, FailingActivateStopsParameterUpdates)
{
  node_->activate_outcome = Outcome::FAILURE;
  node_->configure();
  node_->calls.clear();

  node_->activate();

  EXPECT_EQ(node_->calls, (Sequence{"start", "refresh", "activate", "stop"}));
}

TEST_F(LifecycleNodeTest, FailingDeactivateKeepsParameterUpdates)
{
  node_->deactivate_outcome = Outcome::FAILURE;
  node_->configure();
  node_->activate();
  node_->calls.clear();

  node_->deactivate();

  EXPECT_EQ(node_->calls, (Sequence{"deactivate"}));
}

TEST_F(LifecycleNodeTest, ShutdownFromActiveStopsParameterUpdatesBeforeTheHook)
{
  node_->configure();
  node_->activate();
  node_->calls.clear();

  node_->shutdown();

  EXPECT_EQ(node_->calls, (Sequence{"stop", "shutdown"}));
}

TEST_F(LifecycleNodeTest, ErrorStopsParameterUpdatesBeforeTheHook)
{
  node_->deactivate_outcome = Outcome::THROW;
  node_->configure();
  node_->activate();
  node_->calls.clear();

  node_->deactivate();

  EXPECT_EQ(node_->calls, (Sequence{"deactivate", "stop", "error"}));
}

TEST_F(LifecycleNodeTest, ThrowingActivateStopsParameterUpdatesThroughError)
{
  node_->activate_outcome = Outcome::THROW;
  node_->configure();
  node_->calls.clear();

  node_->activate();

  EXPECT_EQ(node_->calls, (Sequence{"start", "refresh", "activate", "stop", "error"}));
}

TEST_F(LifecycleNodeTest, ShutdownFromUnconfiguredStopsParameterUpdatesBeforeTheHook)
{
  node_->shutdown();

  EXPECT_EQ(node_->calls, (Sequence{"stop", "shutdown"}));
}

TEST_F(LifecycleNodeTest, ShutdownFromInactiveStopsParameterUpdatesBeforeTheHook)
{
  node_->configure();
  node_->calls.clear();

  node_->shutdown();

  EXPECT_EQ(node_->calls, (Sequence{"stop", "shutdown"}));
}

}  // namespace
