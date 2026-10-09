// SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
// SPDX-License-Identifier: Apache-2.0
#include <gtest/gtest.h>

#include <memory>
#include <string>

#include <rclcpp/rclcpp.hpp>

#include "test_nodl_generators/cpp_minimal_node_base.hpp"
#include "test_nodl_generators/cpp_minimal_static_node_base.hpp"
#include "test_nodl_generators/cpp_params_node_base.hpp"

class MinimalNode : public CppMinimalNodeBase
{};

class StaticNode : public CppMinimalStaticNodeBase
{};

class ParamsNode : public CppParamsNodeBase
{
public:
  double max_speed() const
  {
    return params_.max_speed;
  }

  std::string robot_name() const
  {
    return params_.robot_name;
  }
};

class DownstreamTest : public ::testing::Test
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
};

TEST_F(DownstreamTest, SubclassOfExportedBaseRuns)
{
  auto node = std::make_shared<MinimalNode>();

  EXPECT_STREQ(node->get_name(), "cpp_minimal_node");
}

TEST_F(DownstreamTest, SubclassOfExportedParameterizedBaseReadsDefaults)
{
  auto node = std::make_shared<ParamsNode>();

  EXPECT_DOUBLE_EQ(node->max_speed(), 1.5);
  EXPECT_EQ(node->robot_name(), "bot");
}

TEST_F(DownstreamTest, SubclassOfExportedStaticBaseRuns)
{
  auto node = std::make_shared<StaticNode>();

  EXPECT_STREQ(node->get_name(), "cpp_minimal_static_node");
}
