// GENERATED FILE — do not edit. Regenerated from NoDL by nodl_generator_cpp.
#include "my_node_base.hpp"

MyNodeBase::MyNodeBase(const rclcpp::NodeOptions & options)
: nodl_runtime_cpp::LifecycleNode("my_node", options)
, cli_set_bool_(*this, this->create_client<std_srvs::srv::SetBool>("set_bool"))
, action_cli_navigate_(*this, rclcpp_action::create_client<nav2_msgs::action::NavigateToPose>(this, "navigate"))
, sub_cmd_vel_(*this, [this] {
    return this->create_subscription<geometry_msgs::msg::Twist>(
      "cmd_vel",
      rclcpp::QoS(1).best_effort(),
      [this](geometry_msgs::msg::Twist::ConstSharedPtr msg) {
        this->on_cmd_vel(msg);
      });
  })
{}
