# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
cmake_minimum_required(VERSION 3.22)
project(nodl_tutorial_basics)

find_package(ament_cmake REQUIRED)
find_package(ament_nodl REQUIRED)
find_package(nodl_generator_cpp REQUIRED)

ament_nodl_register(talker FILE nodl/talker.nodl.yaml)
nodl_generate_cpp(talker nodl/talker_codegen.nodl.yaml)

add_executable(talker_cpp cpp/talker.cpp)
target_link_libraries(talker_cpp PRIVATE talker)

install(TARGETS talker_cpp
  DESTINATION lib/${PROJECT_NAME})

if(BUILD_TESTING)
  find_package(ament_cmake_pytest REQUIRED)
  ament_add_pytest_test(tutorial_registration_tests test/test_registration.py)
  ament_add_pytest_test(tutorial_runtime_tests test/test_runtime.py TIMEOUT 90)
endif()

ament_package()
