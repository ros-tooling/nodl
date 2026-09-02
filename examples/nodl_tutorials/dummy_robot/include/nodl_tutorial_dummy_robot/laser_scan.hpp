// SPDX-FileCopyrightText: 2017 Open Source Robotics Foundation, Inc.
// SPDX-License-Identifier: Apache-2.0

#pragma once

#include <cmath>
#include <cstddef>

#include "rclcpp/time.hpp"
#include "sensor_msgs/msg/laser_scan.hpp"

namespace nodl_tutorial_dummy_robot
{

inline sensor_msgs::msg::LaserScan make_laser_scan()
{
  constexpr double degrees_to_radians = 3.14159265358979323846 / 180.0;
  constexpr double angle_resolution = 2500.0;
  constexpr double start_angle = -450000.0;
  constexpr double stop_angle = 2250000.0;
  constexpr double scan_frequency = 2500.0;

  sensor_msgs::msg::LaserScan msg;
  msg.header.frame_id = "single_rrbot_hokuyo_link";

  const double angle_range = stop_angle - start_angle;
  double num_values = angle_range / angle_resolution;
  if (static_cast<int>(angle_range) % static_cast<int>(angle_resolution) == 0) {
    ++num_values;
  }
  msg.ranges.resize(static_cast<std::size_t>(num_values));

  msg.time_increment = 0.0F;
  msg.angle_increment = static_cast<float>(angle_resolution / 10000.0 * degrees_to_radians);
  msg.angle_min = static_cast<float>(start_angle / 10000.0 * degrees_to_radians - 3.14159265358979323846 / 2.0);
  msg.angle_max = static_cast<float>(stop_angle / 10000.0 * degrees_to_radians - 3.14159265358979323846 / 2.0);
  msg.scan_time = static_cast<float>(100.0 / scan_frequency);
  msg.range_min = 0.0F;
  msg.range_max = 10.0F;
  return msg;
}

inline void update_laser_scan(
  sensor_msgs::msg::LaserScan & msg, const rclcpp::Time & stamp, double & counter, const int amplitude = 1)
{
  counter += 0.1;
  const auto distance = static_cast<float>(std::abs(amplitude * std::sin(counter)));
  for (auto & range : msg.ranges) {
    range = distance;
  }
  msg.header.stamp = stamp;
}

}  // namespace nodl_tutorial_dummy_robot
