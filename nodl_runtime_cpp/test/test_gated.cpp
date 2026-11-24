// SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
// SPDX-License-Identifier: Apache-2.0
#include <gtest/gtest.h>

#include <atomic>
#include <memory>
#include <stdexcept>
#include <string>
#include <thread>
#include <vector>

#include "lifecycle_msgs/msg/state.hpp"
#include "lifecycle_msgs/srv/get_state.hpp"
#include "nodl_runtime_cpp/gated.hpp"
#include "nodl_runtime_cpp/lifecycle_node.hpp"
#include "rclcpp/rclcpp.hpp"

namespace
{

using CallbackReturn = nodl_runtime_cpp::LifecycleNode::CallbackReturn;
using lifecycle_msgs::msg::State;
using Client = rclcpp::Client<lifecycle_msgs::srv::GetState>;

/// How one hook ends.
enum class Outcome
{
  SUCCESS,
  FAILURE,
  THROW,
};

/// A node whose client is handed out only while it is active, and that records what each hook saw.
class GatedNode : public nodl_runtime_cpp::LifecycleNode
{
public:
  GatedNode()
  : nodl_runtime_cpp::LifecycleNode("gated_node")
  , client_(*this, create_client<lifecycle_msgs::srv::GetState>("peer/get_state"))
  {}

  Outcome activate_outcome = Outcome::SUCCESS;
  Outcome deactivate_outcome = Outcome::SUCCESS;
  /// Whether `get()` was non-null in each hook, as `<hook>=<0|1>`.
  std::vector<std::string> seen;

  std::shared_ptr<Client> client() const
  {
    return client_.get();
  }

  uint8_t state_id()
  {
    return get_current_state().id();
  }

protected:
  CallbackReturn handle_activate(const rclcpp_lifecycle::State &) override
  {
    return record("activate", activate_outcome);
  }

  CallbackReturn handle_deactivate(const rclcpp_lifecycle::State &) override
  {
    return record("deactivate", deactivate_outcome);
  }

private:
  CallbackReturn record(const std::string & name, Outcome outcome)
  {
    seen.push_back(name + "=" + (client_.get() ? "1" : "0"));
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

  nodl_runtime_cpp::Gated<Client> client_;
};

class GatedTest : public ::testing::Test
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

  std::shared_ptr<GatedNode> node_ = std::make_shared<GatedNode>();
};

TEST_F(GatedTest, IsNullUntilTheNodeActivates)
{
  EXPECT_EQ(nullptr, node_->client());
  node_->configure();
  EXPECT_EQ(nullptr, node_->client());
}

TEST_F(GatedTest, IsAvailableInActivateWhileActiveAndInDeactivate)
{
  node_->configure();

  node_->activate();
  EXPECT_NE(nullptr, node_->client());

  node_->deactivate();
  EXPECT_EQ(nullptr, node_->client());
  EXPECT_EQ(node_->seen, (std::vector<std::string>{"activate=1", "deactivate=1"}));
}

TEST_F(GatedTest, ReturnsTheSameEntityOnEveryActivation)
{
  node_->configure();
  node_->activate();
  const auto first = node_->client();
  node_->deactivate();

  node_->activate();

  EXPECT_EQ(first, node_->client());
}

TEST_F(GatedTest, IsNullAfterAFailedActivate)
{
  node_->activate_outcome = Outcome::FAILURE;
  node_->configure();

  EXPECT_EQ(node_->activate().id(), State::PRIMARY_STATE_INACTIVE);

  EXPECT_EQ(nullptr, node_->client());
  EXPECT_EQ(node_->seen, (std::vector<std::string>{"activate=1"}));
}

TEST_F(GatedTest, IsNullAfterAThrowingActivate)
{
  node_->activate_outcome = Outcome::THROW;
  node_->configure();

  node_->activate();

  EXPECT_EQ(nullptr, node_->client());
  EXPECT_EQ(State::PRIMARY_STATE_UNCONFIGURED, node_->state_id());
}

TEST_F(GatedTest, StaysAvailableWhenDeactivateFails)
{
  node_->deactivate_outcome = Outcome::FAILURE;
  node_->configure();
  node_->activate();

  EXPECT_EQ(node_->deactivate().id(), State::PRIMARY_STATE_ACTIVE);

  EXPECT_NE(nullptr, node_->client());
}

TEST_F(GatedTest, IsNullAfterShutdownFromActive)
{
  node_->configure();
  node_->activate();

  node_->shutdown();

  EXPECT_EQ(nullptr, node_->client());
}

TEST_F(GatedTest, IsNullAfterErrorFromActive)
{
  node_->deactivate_outcome = Outcome::THROW;
  node_->configure();
  node_->activate();

  node_->deactivate();

  EXPECT_EQ(State::PRIMARY_STATE_UNCONFIGURED, node_->state_id());
  EXPECT_EQ(nullptr, node_->client());
}

TEST_F(GatedTest, IsAvailableAgainAfterReactivation)
{
  node_->configure();
  node_->activate();
  node_->deactivate();
  ASSERT_EQ(nullptr, node_->client());

  node_->activate();

  EXPECT_NE(nullptr, node_->client());
}

TEST_F(GatedTest, ACopyObtainedWhileActiveStaysUsableAfterDeactivation)
{
  node_->configure();
  node_->activate();
  const auto copy = node_->client();

  node_->deactivate();

  EXPECT_NE(nullptr, copy);
  EXPECT_FALSE(copy->service_is_ready());
}

TEST_F(GatedTest, ConstructingWhileActiveThrows)
{
  node_->configure();
  node_->activate();

  EXPECT_THROW(nodl_runtime_cpp::Gated<Client> late(*node_, std::shared_ptr<Client>()), std::logic_error);
}

TEST_F(GatedTest, DestroyingWhileActiveUnregistersTheSlot)
{
  auto node = std::make_shared<nodl_runtime_cpp::LifecycleNode>("plain_node");
  auto gated = std::make_unique<nodl_runtime_cpp::Gated<Client>>(*node, std::shared_ptr<Client>());
  node->configure();
  node->activate();

  EXPECT_NO_THROW(gated.reset());
  EXPECT_NO_THROW(node->deactivate());
}

TEST_F(GatedTest, GetFromAnotherThreadWhileTransitionsCycleNeverFails)
{
  node_->configure();
  std::atomic<bool> stop{false};
  std::atomic<int> reads{0};
  std::thread reader([&] {
    while (!stop) {
      // A non-null result must be the entity itself.
      const auto client = node_->client();
      if (client) {
        EXPECT_FALSE(client->service_is_ready());
      }
      ++reads;
    }
  });

  for (int cycle = 0; cycle < 500; ++cycle) {
    node_->activate();
    node_->deactivate();
  }
  stop = true;
  reader.join();

  EXPECT_GT(reads, 0);
  EXPECT_EQ(nullptr, node_->client());
}

}  // namespace
