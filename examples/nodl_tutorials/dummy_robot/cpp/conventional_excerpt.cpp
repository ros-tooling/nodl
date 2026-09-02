// SPDX-FileCopyrightText: 2017 Open Source Robotics Foundation, Inc.
// SPDX-License-Identifier: Apache-2.0

#include <cmath>

#include "rclcpp/rclcpp.hpp"
#include "sensor_msgs/msg/laser_scan.hpp"

auto node = rclcpp::Node::make_shared("dummy_laser");

// [Interface] The handwritten node chooses the topic, type, and QoS.
auto laser_pub = node->create_publisher<sensor_msgs::msg::LaserScan>("scan", 10);

// [Behavior] The application owns its execution rate and scan data.
rclcpp::WallRate loop_rate(30);
sensor_msgs::msg::LaserScan msg;
// Existing frame, angle, range, and timing initialization.

while (rclcpp::ok()) {
  counter += 0.1;
  const auto distance = static_cast<float>(std::abs(amplitude * std::sin(counter)));
  for (auto & range : msg.ranges) {
    range = distance;
  }
  msg.header.stamp = clock->now();

  laser_pub->publish(msg);
  executor.spin_some();
  loop_rate.sleep();
}
