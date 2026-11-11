// GENERATED FILE — do not edit. Regenerated from NoDL by nodl_generator_cpp.
#include "my_node_base.hpp"

#include "rclcpp/create_publisher.hpp"

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

  // Register action clients
  manage(action_cli_navigate_, [this] {
    return rclcpp_action::create_client<nav2_msgs::action::NavigateToPose>(this, "navigate");
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

  // Register action servers
  manage_action_server<example_interfaces::action::Fibonacci>(
    action_srv_fibonacci_,
    [this](nodl_runtime_cpp::GoalTracker<example_interfaces::action::Fibonacci> & tracker) {
      return rclcpp_action::create_server<example_interfaces::action::Fibonacci>(
        this,
        "fibonacci",
        [this](const rclcpp_action::GoalUUID & uuid, std::shared_ptr<const example_interfaces::action::Fibonacci::Goal> goal) {
          return this->on_fibonacci_goal(uuid, goal);
        },
        [this](std::shared_ptr<rclcpp_action::ServerGoalHandle<example_interfaces::action::Fibonacci>> goal_handle) {
          return this->on_fibonacci_cancel(goal_handle);
        },
        tracker.accepted([this](std::shared_ptr<rclcpp_action::ServerGoalHandle<example_interfaces::action::Fibonacci>> goal_handle) {
          this->on_fibonacci_accepted(goal_handle);
        }));
    });
}
