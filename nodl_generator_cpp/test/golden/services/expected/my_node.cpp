// GENERATED FILE — do not edit. Regenerated from NoDL by nodl_generator_cpp.
#include "my_node.hpp"

MyNodeBase::MyNodeBase(const rclcpp::NodeOptions & options)
: rclcpp::Node("my_node", options)
{

  // Create service servers
  srv_trigger_ = this->create_service<std_srvs::srv::Trigger>(
    "trigger",
    [this](std_srvs::srv::Trigger::Request::SharedPtr req, std_srvs::srv::Trigger::Response::SharedPtr res) {
      this->on_trigger(req, res);
    });

  // Create service clients
  cli_set_bool_ = this->create_client<std_srvs::srv::SetBool>("set_bool");
}
