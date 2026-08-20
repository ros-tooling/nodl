// GENERATED FILE — do not edit. Regenerated from NoDL by nodl_generator_cpp.
#include "my_node.hpp"

MyNodeBase::MyNodeBase(const rclcpp::NodeOptions & options)
: rclcpp::Node("my_node", options)
{

  // Create publishers
  pub_status_ = this->create_publisher<std_msgs::msg::String>("status", rclcpp::QoS(10).reliable());

  // Create subscriptions
  sub_cmd_vel_ = this->create_subscription<geometry_msgs::msg::Twist>(
    "cmd_vel",
    rclcpp::QoS(1).best_effort(),
    [this](geometry_msgs::msg::Twist::ConstSharedPtr msg) {
      this->on_cmd_vel(msg);
    });
}
