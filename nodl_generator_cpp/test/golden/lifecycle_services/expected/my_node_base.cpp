// GENERATED FILE — do not edit. Regenerated from NoDL by nodl_generator_cpp.
#include "my_node_base.hpp"
#include <nodl_runtime_cpp/gated_subscription.hpp>
#include <nodl_runtime_cpp/gated_service.hpp>

MyNodeBase::MyNodeBase(const rclcpp::NodeOptions & options)
: nodl_runtime_cpp::LifecycleNode("my_node", options)
{

  // Create subscriptions
  sub_cmd_vel_ = this->create_subscription<geometry_msgs::msg::Twist>(
    "cmd_vel",
    rclcpp::QoS(1).best_effort(),
    nodl_runtime_cpp::gate_subscription_callback<geometry_msgs::msg::Twist>(
      this->gate(),
      [this](geometry_msgs::msg::Twist::ConstSharedPtr msg) {
        this->on_cmd_vel(msg);
      }));

  // Create service servers
  srv_trigger_ = nodl_runtime_cpp::create_gated_service<std_srvs::srv::Trigger>(
    *this,
    this->gate(),
    "trigger",
    [this](std_srvs::srv::Trigger::Request::SharedPtr req, std_srvs::srv::Trigger::Response::SharedPtr res) {
      this->on_trigger(req, res);
    });
}
