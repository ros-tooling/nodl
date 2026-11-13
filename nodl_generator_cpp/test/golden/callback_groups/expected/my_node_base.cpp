// GENERATED FILE — do not edit. Regenerated from NoDL by nodl_generator_cpp.
#include "my_node_base.hpp"

MyNodeBase::MyNodeBase(const rclcpp::NodeOptions & options)
: rclcpp::Node("my_node", options)
{

  // Create callback groups before their endpoints.
  nodl_callback_group_control_ = this->create_callback_group(rclcpp::CallbackGroupType::MutuallyExclusive);
  nodl_callback_group_processing_ = this->create_callback_group(rclcpp::CallbackGroupType::Reentrant);

  // Create subscriptions
  rclcpp::SubscriptionOptions sub_work_options;
  sub_work_options.callback_group = nodl_callback_group_processing_;
  sub_work_ = this->create_subscription<std_msgs::msg::Empty>(
    "work",
    rclcpp::QoS(10).reliable(),
    [this](std_msgs::msg::Empty::ConstSharedPtr msg) {
      this->on_work(msg);
    }, sub_work_options);

  // Create service servers
  srv_status_ = this->create_service<std_srvs::srv::Trigger>(
    "status",
    [this](std_srvs::srv::Trigger::Request::SharedPtr req, std_srvs::srv::Trigger::Response::SharedPtr res) {
      this->on_status(req, res);
    }, rmw_qos_profile_services_default, nodl_callback_group_control_);
}
