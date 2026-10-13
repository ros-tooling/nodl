# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
cmake_minimum_required(VERSION 3.22)
project(nodl_tutorial_lifecycle_action_py)

find_package(ament_cmake REQUIRED)
find_package(ament_nodl REQUIRED)
find_package(nodl_generator_py REQUIRED)

nodl_generate_py(
  fibonacci_action_server_py_base
  ../nodl/fibonacci.nodl.yaml
  RESOURCE_NAME fibonacci)

install(PROGRAMS fibonacci_action_server.py
  DESTINATION lib/${PROJECT_NAME}
  RENAME fibonacci_action_server_py)

if(BUILD_TESTING)
  find_package(ament_cmake_pytest REQUIRED)
  ament_add_pytest_test(tutorial_registration_tests ../test/test_registration.py)
  ament_add_pytest_test(tutorial_runtime_tests ../test/test_runtime.py
    TIMEOUT 180)
endif()

ament_package()
