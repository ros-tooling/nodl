# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
cmake_minimum_required(VERSION 3.22)
project(nodl_common_interfaces)

find_package(ament_cmake REQUIRED)
find_package(ament_nodl REQUIRED)

ament_nodl_register(node
  FILE nodl/rclcpp_node.nodl.yaml
  PACKAGE rclcpp)

ament_nodl_register(lifecycle_node
  FILE nodl/rclcpp_lifecycle_node.nodl.yaml
  PACKAGE rclcpp_lifecycle)

ament_package()
