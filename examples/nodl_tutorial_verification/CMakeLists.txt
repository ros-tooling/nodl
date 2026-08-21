# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
cmake_minimum_required(VERSION 3.22)
project(nodl_tutorial_verification)

find_package(ament_cmake REQUIRED)
find_package(ament_nodl REQUIRED)

ament_nodl_register_node(talker FILE nodl/talker.nodl.yaml)
ament_nodl_register_node(dummy_laser FILE nodl/dummy_laser.nodl.yaml)

if(BUILD_TESTING)
  find_package(ament_cmake_pytest REQUIRED)
  ament_add_pytest_test(tutorial_registration_tests test/test_registration.py)
endif()

ament_package()
