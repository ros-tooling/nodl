// GENERATED FILE — do not edit. Regenerated from NoDL by nodl_generator_cpp.
#include "my_node_base.hpp"

MyNodeBase::MyNodeBase(const rclcpp::NodeOptions & options)
: nodl_runtime_cpp::LifecycleNode("my_node", options)
{

  // Create publishers
  pub_status_ = this->create_publisher<std_msgs::msg::String>("status", rclcpp::QoS(10).reliable());

  // Register subscriptions
  manage(sub_cmd_vel_, [this] {
    return this->create_subscription<geometry_msgs::msg::Twist>(
      "cmd_vel",
      rclcpp::QoS(1).best_effort(),
      [this](geometry_msgs::msg::Twist::ConstSharedPtr msg) {
        this->on_cmd_vel(msg);
      });
  });
  manage(sub_latched_, [this] {
    return this->create_subscription<std_msgs::msg::String>(
      "latched",
      rclcpp::QoS(1).reliable().transient_local(),
      [this](std_msgs::msg::String::ConstSharedPtr msg) {
        this->on_latched(msg);
      });
  });

  // Create service servers
  srv_trigger_ = this->create_service<std_srvs::srv::Trigger>(
    "trigger",
    [this](std_srvs::srv::Trigger::Request::SharedPtr req, std_srvs::srv::Trigger::Response::SharedPtr res) {
      this->on_trigger(req, res);
    });
}
