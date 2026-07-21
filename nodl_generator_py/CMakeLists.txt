# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
cmake_minimum_required(VERSION 3.16)
project(nodl_generator_py)

find_package(ament_cmake REQUIRED)
find_package(ament_cmake_python REQUIRED)

# Importable helper for ament_python users.
ament_python_install_package(${PROJECT_NAME})

# Generator CLI used by the CMake function.
install(
  PROGRAMS scripts/nodl_generate_py
  DESTINATION lib/${PROJECT_NAME}
)

install(
  DIRECTORY templates/
  DESTINATION share/${PROJECT_NAME}/templates
)

install(
  FILES cmake/nodl_generate_py.cmake
  DESTINATION share/${PROJECT_NAME}/cmake
)

if(BUILD_TESTING)
  find_package(ament_cmake_pytest REQUIRED)
  ament_add_pytest_test(test_generator test/test_generator.py)
endif()

ament_package(
  CONFIG_EXTRAS "nodl_generator_py-extras.cmake.in"
)
