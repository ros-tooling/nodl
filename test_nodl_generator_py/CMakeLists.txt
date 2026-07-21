# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
cmake_minimum_required(VERSION 3.16)
project(test_nodl_generator_py)

find_package(ament_cmake REQUIRED)
find_package(nodl_generator_py REQUIRED)

if(BUILD_TESTING)
  find_package(ament_cmake_pytest REQUIRED)

  nodl_generate_py(pubsub_node fixtures/pubsub_node.nodl.yaml)
  set(_test_pythonpath "${CMAKE_CURRENT_BINARY_DIR}/nodl_generated/pubsub_node")
  string(APPEND _test_pythonpath ":${CMAKE_CURRENT_SOURCE_DIR}/derived")
  ament_add_pytest_test(
    test_pubsub test/test_pubsub.py
    APPEND_ENV PYTHONPATH=${_test_pythonpath}
  )
endif()

ament_package()
