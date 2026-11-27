# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
cmake_minimum_required(VERSION 3.22)
project(nodl_tutorial_lifecycle_action_cpp)

find_package(ament_cmake REQUIRED)
find_package(ament_nodl REQUIRED)
find_package(nodl_generator_cpp REQUIRED)

nodl_generate_cpp(
  fibonacci_action_server_cpp_base
  RESOURCE_NAME fibonacci
  ../nodl/fibonacci.nodl.yaml)

add_executable(fibonacci_action_server_cpp fibonacci_action_server.cpp)
target_link_libraries(fibonacci_action_server_cpp PRIVATE fibonacci_action_server_cpp_base)
install(TARGETS fibonacci_action_server_cpp
  DESTINATION lib/${PROJECT_NAME})

if(BUILD_TESTING)
  find_package(ament_cmake_pytest REQUIRED)
  ament_add_pytest_test(tutorial_registration_tests ../test/test_registration.py)
  ament_add_pytest_test(tutorial_runtime_tests ../test/test_runtime.py
    TIMEOUT 180)
endif()

ament_package()
