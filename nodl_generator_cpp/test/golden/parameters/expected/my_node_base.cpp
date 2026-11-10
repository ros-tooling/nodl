// GENERATED FILE — do not edit. Regenerated from NoDL by nodl_generator_cpp.
#include "my_node_base.hpp"

MyNodeBase::MyNodeBase(const rclcpp::NodeOptions & options)
: rclcpp::Node("my_node", options)
, param_listener_(this->get_node_parameters_interface(), this->get_logger())
, params_(param_listener_.get_params())
{
  param_listener_.setUserCallback([this](const my_node_base::Params & params) {
    {
      const auto current = params_.lock();
      if (params.max_speed == current->max_speed &&
          params.robot_name == current->robot_name &&
          params.enabled == current->enabled &&
          params.colour.r == current->colour.r &&
          params.colour.g == current->colour.g) {
        return;
      }
      *current = params;
    }
    this->on_parameters_changed(params);
  });

  // Create publishers
  pub_status_ = this->create_publisher<std_msgs::msg::String>("status", rclcpp::QoS(10).reliable());
}
