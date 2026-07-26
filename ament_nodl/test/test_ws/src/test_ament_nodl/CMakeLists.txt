# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
cmake_minimum_required(VERSION 3.22)
project(test_ament_nodl)

find_package(ament_cmake REQUIRED)
find_package(ament_nodl REQUIRED)

# --- ament_nodl_install ---
# Install multiple NoDL files; validates at build time.
ament_nodl_install(
  FILES
    nodl/base_interfaces.nodl.yaml
    nodl/diagnostics.nodl.yaml
)

# --- ament_nodl_register_executable ---
# Register a NoDL file for a standalone executable.
ament_nodl_register_executable(sensor_driver
  FILE nodl/sensor_driver.nodl.yaml
)

# --- ament_nodl_register_component ---
# Register a NoDL file for a composable node component.
ament_nodl_register_component(test_ament_nodl::MotorController
  FILE nodl/motor_controller.nodl.yaml
)

# Non-YAML frontend: the macros should be extension-agnostic.
ament_nodl_install(
  FILES
    nodl/json_node.nodl.json
)

ament_package()
