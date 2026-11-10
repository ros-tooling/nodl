// GENERATED FILE — do not edit. Regenerated from NoDL by nodl_generator_cpp.
#include "my_node_base.hpp"

namespace my_pkg::nodes
{
MyNodeBase::MyNodeBase(const rclcpp::NodeOptions & options)
: rclcpp::Node("my_node", options)
, param_listener_(this->get_node_parameters_interface(), this->get_logger())
, params_(param_listener_.get_params())
{
  param_listener_.setUserCallback([this](const my_node_base::Params & params) {
    {
      const auto current = params_.lock();
      if (nodl_runtime_cpp::values_equal(params.max_speed, current->max_speed) &&
          nodl_runtime_cpp::values_equal(params.colour.r, current->colour.r)) {
        return;
      }
      *current = params;
    }
    this->on_parameters_changed(params);
  });

  // Create publishers
  pub_status_ = this->create_publisher<std_msgs::msg::String>("status", rclcpp::QoS(10).reliable());
}

}  // namespace my_pkg::nodes
