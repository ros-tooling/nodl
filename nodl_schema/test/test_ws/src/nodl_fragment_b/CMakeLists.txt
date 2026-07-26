# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
cmake_minimum_required(VERSION 3.22)
project(nodl_fragment_b)

find_package(ament_cmake REQUIRED)
find_package(nodl_schema REQUIRED)

ament_nodl_install(
  FILES
    nodl/sensors.nodl.yaml
)

ament_package()
