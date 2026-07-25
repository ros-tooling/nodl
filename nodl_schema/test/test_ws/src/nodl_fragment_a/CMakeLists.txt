# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
cmake_minimum_required(VERSION 3.22)
project(nodl_fragment_a)

find_package(ament_cmake REQUIRED)
find_package(ament_nodl REQUIRED)

ament_nodl_install(
  FILES
    nodl/diagnostics.nodl.yaml
    nodl/shared_base.nodl.yaml
)

ament_package()
