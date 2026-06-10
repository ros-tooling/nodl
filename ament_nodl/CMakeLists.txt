# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
cmake_minimum_required(VERSION 3.22)
project(ament_nodl)

find_package(ament_cmake REQUIRED)

install(FILES
  cmake/ament_nodl_register_document.cmake
  cmake/ament_nodl_register_node.cmake
  DESTINATION share/${PROJECT_NAME}/cmake)

install(FILES package.xml
  DESTINATION share/${PROJECT_NAME})

ament_package(CONFIG_EXTRAS "ament_nodl-extras.cmake.in")
