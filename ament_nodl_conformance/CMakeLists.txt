# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0

cmake_minimum_required(VERSION 3.22)
project(ament_nodl_conformance)

find_package(ament_cmake REQUIRED)

install(FILES
  cmake/nodl_add_conformance_test.cmake
  cmake/nodl_conformance_test.py.in
  DESTINATION share/${PROJECT_NAME}/cmake)

if(BUILD_TESTING)
  find_package(ament_cmake_pytest REQUIRED)
  ament_add_pytest_test(test_cmake test/test_cmake.py)
endif()

ament_package(CONFIG_EXTRAS "ament_nodl_conformance-extras.cmake.in")
