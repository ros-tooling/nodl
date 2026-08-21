// SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
// SPDX-License-Identifier: Apache-2.0

#include <memory>

#include "rcl_interfaces/msg/parameter_descriptor.hpp"
#include "rclcpp/rclcpp.hpp"
#include "std_msgs/msg/string.hpp"
#include "std_srvs/srv/empty.hpp"

class FixtureNode : public rclcpp::Node
{
public:
  FixtureNode()
  : Node("fixture")
  {
    const auto qos = rclcpp::QoS(rclcpp::KeepLast(10)).reliable().durability_volatile();
    publisher_ = create_publisher<std_msgs::msg::String>("state", qos);
    subscription_ =
      create_subscription<std_msgs::msg::String>("command", qos, [](std_msgs::msg::String::ConstSharedPtr) {});
    service_ = create_service<std_srvs::srv::Empty>(
      "reset", [](std_srvs::srv::Empty::Request::SharedPtr, std_srvs::srv::Empty::Response::SharedPtr) {});
    client_ = create_client<std_srvs::srv::Empty>("calibrate");

    rcl_interfaces::msg::ParameterDescriptor descriptor;
    descriptor.read_only = true;
    declare_parameter<int64_t>("limit", 10, descriptor);
  }

private:
  rclcpp::Publisher<std_msgs::msg::String>::SharedPtr publisher_;
  rclcpp::Subscription<std_msgs::msg::String>::SharedPtr subscription_;
  rclcpp::Service<std_srvs::srv::Empty>::SharedPtr service_;
  rclcpp::Client<std_srvs::srv::Empty>::SharedPtr client_;
};

int main(int argc, char ** argv)
{
  rclcpp::init(argc, argv);
  rclcpp::spin(std::make_shared<FixtureNode>());
  rclcpp::shutdown();
  return 0;
}
