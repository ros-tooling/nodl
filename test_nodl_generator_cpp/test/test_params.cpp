#include <memory>
#include <string>

#include <gtest/gtest.h>
#include <rclcpp/rclcpp.hpp>

#include "params_node_derived.hpp"

class ParamsAxis : public ::testing::Test
{
protected:
  void SetUp() override { rclcpp::init(0, nullptr); }
  void TearDown() override { rclcpp::shutdown(); }
};

TEST_F(ParamsAxis, DefaultsPopulated)
{
  auto node = std::make_shared<ParamsNode>();
  EXPECT_DOUBLE_EQ(node->params_.publish_rate, 10.0);
  EXPECT_EQ(node->params_.frame_id, std::string("base_link"));
  EXPECT_TRUE(node->params_.enabled);
}

TEST_F(ParamsAxis, ParametersDeclaredOnNode)
{
  auto node = std::make_shared<ParamsNode>();
  EXPECT_TRUE(node->has_parameter("publish_rate"));
  EXPECT_TRUE(node->has_parameter("frame_id"));
  EXPECT_TRUE(node->has_parameter("enabled"));
}

TEST_F(ParamsAxis, ReadOnlyFlagPropagated)
{
  auto node = std::make_shared<ParamsNode>();
  EXPECT_TRUE(node->describe_parameter("enabled").read_only);
  // Sanity: non-read-only params surface as writable.
  EXPECT_FALSE(node->describe_parameter("publish_rate").read_only);
}
