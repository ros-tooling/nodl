// GENERATED FILE — do not edit. Regenerated from NoDL by nodl_generator_cpp.
#include "my_node_base.hpp"

MyNodeBase::MyNodeBase(const rclcpp::NodeOptions & options)
: nodl_runtime_cpp::LifecycleNode("my_node", options)
, param_listener_(this->get_node_parameters_interface(), this->get_logger())
, params_(param_listener_.get_params())
{
}

void MyNodeBase::refresh_parameters()
{
  *params_.lock() = param_listener_.get_params();
}

void MyNodeBase::start_parameter_updates()
{
  param_listener_.setUserCallback([this](const my_node_base::Params & params) {
    {
      const auto current = params_.lock();
      if (nodl_runtime_cpp::values_equal(params.max_speed, current->max_speed)) {
        return;
      }
      *current = params;
    }
    this->on_parameters_changed(params);
  });
}

void MyNodeBase::stop_parameter_updates()
{
  param_listener_.clearUserCallback();
}
