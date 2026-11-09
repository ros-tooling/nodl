// GENERATED FILE — do not edit. Regenerated from NoDL by nodl_generator_cpp.
#include "my_node_base.hpp"

MyNodeBase::MyNodeBase(const rclcpp::NodeOptions & options)
: nodl_runtime_cpp::LifecycleNode("my_node", options)
{

  // Create service clients
  cli_add_ = std::make_shared<nodl_runtime_cpp::GatedClient<example_interfaces::srv::AddTwoInts>>(
    this->gate(),
    this->create_client<example_interfaces::srv::AddTwoInts>("add"));

  // Create action clients
  action_cli_navigate_ = std::make_shared<nodl_runtime_cpp::GatedActionClient<nav2_msgs::action::NavigateToPose>>(
    this->gate(),
    rclcpp_action::create_client<nav2_msgs::action::NavigateToPose>(this, "navigate"));
}
