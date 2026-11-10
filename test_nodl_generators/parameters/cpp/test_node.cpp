// SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
// SPDX-License-Identifier: Apache-2.0
#include <gtest/gtest.h>

#include <memory>
#include <string>
#include <vector>

#include "rclcpp/rclcpp.hpp"
#include "test_nodl_generators/cpp_params_node_base.hpp"

/// Reads its parameters through the lock, and records the values that `on_parameters_changed` receives.
class TestNode : public CppParamsNodeBase
{
public:
  /// Reads one field.
  double max_speed() const
  {
    return params_.lock()->max_speed;
  }

  /// Takes a consistent snapshot of several fields.
  std::string summary() const
  {
    const cpp_params_node_base::Params snapshot = *params_.lock();
    return snapshot.robot_name + (snapshot.enabled ? ":on" : ":off");
  }

  /// The latest values, read from the listener.
  double listener_max_speed() const
  {
    return param_listener().get_params().max_speed;
  }

  /// The `max_speed` that each call of the hook received.
  std::vector<double> notified_max_speeds;

  /// The `max_speed` that the hook read from `params_`, which it can lock.
  std::vector<double> locked_max_speeds;

protected:
  void on_parameters_changed(const cpp_params_node_base::Params & params) override
  {
    notified_max_speeds.push_back(params.max_speed);
    locked_max_speeds.push_back(params_.lock()->max_speed);
  }
};

class GeneratedParameters : public ::testing::Test
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

  std::shared_ptr<TestNode> node_ = std::make_shared<TestNode>();
};

TEST_F(GeneratedParameters, StartsWithDefaults)
{
  EXPECT_DOUBLE_EQ(node_->max_speed(), 1.5);
  EXPECT_EQ(node_->summary(), "bot:on");
  EXPECT_TRUE(node_->notified_max_speeds.empty());
}

TEST_F(GeneratedParameters, FollowsDynamicChangesAndNotifiesOnce)
{
  const auto result = node_->set_parameter(rclcpp::Parameter("max_speed", 2.5));

  ASSERT_TRUE(result.successful) << result.reason;
  EXPECT_DOUBLE_EQ(node_->max_speed(), 2.5);
  EXPECT_DOUBLE_EQ(node_->listener_max_speed(), 2.5);
  EXPECT_EQ(node_->notified_max_speeds, std::vector<double>{2.5});
  EXPECT_EQ(node_->locked_max_speeds, std::vector<double>{2.5});
}

TEST_F(GeneratedParameters, SnapshotIsConsistentAfterSeveralChanges)
{
  ASSERT_TRUE(node_->set_parameter(rclcpp::Parameter("enabled", false)).successful);

  EXPECT_EQ(node_->summary(), "bot:off");
}

TEST_F(GeneratedParameters, RejectedValueChangesNothingAndDoesNotNotify)
{
  const auto result = node_->set_parameter(rclcpp::Parameter("max_speed", -1.0));

  EXPECT_FALSE(result.successful);
  EXPECT_DOUBLE_EQ(node_->max_speed(), 1.5);
  EXPECT_DOUBLE_EQ(node_->listener_max_speed(), 1.5);
  EXPECT_TRUE(node_->notified_max_speeds.empty());
}

TEST_F(GeneratedParameters, IgnoresParametersThatAreNotDeclaredInTheDocument)
{
  node_->declare_parameter("unrelated", 1);

  ASSERT_TRUE(node_->set_parameter(rclcpp::Parameter("unrelated", 2)).successful);

  EXPECT_TRUE(node_->notified_max_speeds.empty());
}

TEST_F(GeneratedParameters, IgnoresASetThatChangesNoDeclaredValue)
{
  ASSERT_TRUE(node_->set_parameter(rclcpp::Parameter("max_speed", 1.5)).successful);

  EXPECT_TRUE(node_->notified_max_speeds.empty());
}
