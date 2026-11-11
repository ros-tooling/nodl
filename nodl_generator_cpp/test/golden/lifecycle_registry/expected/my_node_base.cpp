// GENERATED FILE — do not edit. Regenerated from NoDL by nodl_generator_cpp.
#include "my_node_base.hpp"

#include <rclcpp/create_publisher.hpp>

MyNodeBase::MyNodeBase(const rclcpp::NodeOptions & options)
: nodl_runtime_cpp::LifecycleNode("my_node", options)
{

  // Register publishers
  manage(pub_status_, [this] {
    return rclcpp::create_publisher<std_msgs::msg::String>(*this, "status", rclcpp::QoS(10).reliable());
  });

  // Register service clients
  manage(cli_set_bool_, [this] {
    return this->create_client<std_srvs::srv::SetBool>("set_bool");
  });

  // Register subscriptions
  manage(sub_cmd_vel_, [this] {
    return this->create_subscription<geometry_msgs::msg::Twist>(
      "cmd_vel",
      rclcpp::QoS(1).best_effort(),
      [this](geometry_msgs::msg::Twist::ConstSharedPtr msg) {
        this->on_cmd_vel(msg);
      });
  });

  // Register service servers
  manage(srv_trigger_, [this] {
    return this->create_service<std_srvs::srv::Trigger>(
      "trigger",
      [this](std_srvs::srv::Trigger::Request::SharedPtr req, std_srvs::srv::Trigger::Response::SharedPtr res) {
        this->on_trigger(req, res);
      });
  });
}
