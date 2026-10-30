# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
cmake_minimum_required(VERSION 3.22)
project(ament_nodl)

find_package(ament_cmake REQUIRED)
find_package(ament_cmake_python REQUIRED)

ament_python_install_package(${PROJECT_NAME})

install(
  DIRECTORY cmake
  DESTINATION share/${PROJECT_NAME}
)

install(FILES package.xml
  DESTINATION share/${PROJECT_NAME})

if(BUILD_TESTING)
  find_package(ament_cmake_pytest REQUIRED)
  ament_add_pytest_test(test_conformance_cmake test/test_conformance_cmake.py)
  ament_add_pytest_test(test_testing test/test_testing.py)
endif()

ament_package(CONFIG_EXTRAS "ament_nodl-extras.cmake.in")
