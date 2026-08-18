# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
cmake_minimum_required(VERSION 3.22)
project(nodl_base_descriptions)

find_package(ament_cmake REQUIRED)
find_package(ament_nodl REQUIRED)

# Register base-class NoDL descriptions under the upstream package names. When the upstream packages eventually
# ship their own .nodl.yaml files, this package can be removed.

ament_nodl_register_node(node
  FILE nodl/rclcpp_node.nodl.yaml
  PACKAGE rclcpp)

# WORKAROUND: The lifecycle node file includes nodl://rclcpp/node, which
# isn't in the ament index at build time (it's co-installed by this same
# package). The ament_nodl_register_node macro validates includes at build
# time and would fail. We install manually to skip validation.
#
# Once nodl_schema supports local file references, the lifecycle file can
# use a relative path for its include and the macro will work normally.
install(
  FILES nodl/rclcpp_lifecycle_node.nodl.yaml
  DESTINATION "share/ament_index/resource_index/nodl_nodes"
  RENAME "rclcpp_lifecycle__lifecycle_node")
install(
  FILES nodl/rclcpp_lifecycle_node.nodl.yaml
  DESTINATION "share/rclcpp_lifecycle/nodl")

ament_package()
