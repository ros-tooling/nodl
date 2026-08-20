// GENERATED FILE — do not edit. Regenerated from NoDL by nodl_generator_cpp.
#include "my_node.hpp"

MyNodeBase::MyNodeBase(const rclcpp::NodeOptions & options)
: rclcpp::Node("my_node", options)
, param_listener_(this->get_node_parameters_interface(), this->get_logger())
, params_(param_listener_.get_params())
{

  // Create publishers
  pub_status_ = this->create_publisher<std_msgs::msg::String>("status", rclcpp::QoS(10).reliable());

  // Create subscriptions
  sub_cmd_vel_ = this->create_subscription<geometry_msgs::msg::Twist>(
    "cmd_vel",
    rclcpp::QoS(1).best_effort(),
    [this](geometry_msgs::msg::Twist::ConstSharedPtr msg) {
      this->on_cmd_vel(msg);
    });

  // Create service servers
  srv_trigger_ = this->create_service<std_srvs::srv::Trigger>(
    "trigger",
    [this](std_srvs::srv::Trigger::Request::SharedPtr req, std_srvs::srv::Trigger::Response::SharedPtr res) {
      this->on_trigger(req, res);
    });

  // Create service clients
  cli_set_bool_ = this->create_client<std_srvs::srv::SetBool>("set_bool");

  // Create action servers
  action_srv_fibonacci_ = rclcpp_action::create_server<example_interfaces::action::Fibonacci>(
    this,
    "fibonacci",
    [this](const rclcpp_action::GoalUUID & uuid, std::shared_ptr<const example_interfaces::action::Fibonacci::Goal> goal) {
      return this->on_fibonacci_goal(uuid, goal);
    },
    [this](std::shared_ptr<rclcpp_action::ServerGoalHandle<example_interfaces::action::Fibonacci>> goal_handle) {
      return this->on_fibonacci_cancel(goal_handle);
    },
    [this](std::shared_ptr<rclcpp_action::ServerGoalHandle<example_interfaces::action::Fibonacci>> goal_handle) {
      this->on_fibonacci_accepted(goal_handle);
    });

  // Create action clients
  action_cli_navigate_ = rclcpp_action::create_client<nav2_msgs::action::NavigateToPose>(this, "navigate");
}
