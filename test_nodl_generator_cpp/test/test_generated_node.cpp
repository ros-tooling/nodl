#include "test_node.hpp"

#include <memory>
#include <string>

#include <gtest/gtest.h>
#include <rclcpp/rclcpp.hpp>
#include <std_msgs/msg/string.hpp>

// Minimal concrete subclass.  Re-exports protected members as public so the
// tests can verify them directly.
class ConcreteTestNode : public TestNodeBase
{
public:
  using TestNodeBase::TestNodeBase;

  // Re-export protected members for white-box testing
  using TestNodeBase::params_;
  using TestNodeBase::pub_output_;

  int input_count{0};

protected:
  void on_input(std_msgs::msg::String::ConstSharedPtr /*msg*/) override
  {
    ++input_count;
  }
};

class GeneratedNodeTest : public ::testing::Test
{
protected:
  void SetUp() override { rclcpp::init(0, nullptr); }
  void TearDown() override { rclcpp::shutdown(); }
};

TEST_F(GeneratedNodeTest, NodeNameMatchesNodlFile)
{
  auto node = std::make_shared<ConcreteTestNode>();
  EXPECT_STREQ(node->get_name(), "test_node");
}

TEST_F(GeneratedNodeTest, PublisherExists)
{
  auto node = std::make_shared<ConcreteTestNode>();
  ASSERT_NE(node->pub_output_, nullptr);
}

TEST_F(GeneratedNodeTest, DefaultParameterValues)
{
  auto node = std::make_shared<ConcreteTestNode>();
  // Params struct is populated by generate_parameter_library at construction
  EXPECT_DOUBLE_EQ(node->params_.publish_rate, 10.0);
  EXPECT_EQ(node->params_.frame_id, std::string("base_link"));
  EXPECT_TRUE(node->params_.enabled);
}

TEST_F(GeneratedNodeTest, ParametersDeclaredOnNode)
{
  auto node = std::make_shared<ConcreteTestNode>();
  EXPECT_TRUE(node->has_parameter("publish_rate"));
  EXPECT_TRUE(node->has_parameter("frame_id"));
  EXPECT_TRUE(node->has_parameter("enabled"));
}

TEST_F(GeneratedNodeTest, ReadOnlyParameterIsReadOnly)
{
  auto node = std::make_shared<ConcreteTestNode>();
  auto desc = node->describe_parameter("enabled");
  EXPECT_TRUE(desc.read_only);
}
