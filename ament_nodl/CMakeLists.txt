# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
cmake_minimum_required(VERSION 3.22)
project(ament_nodl)

find_package(ament_cmake REQUIRED)

install(FILES
  cmake/ament_nodl_install.cmake
  cmake/ament_nodl_package_hook.cmake
  cmake/ament_nodl_register_executable.cmake
  cmake/ament_nodl_register_component.cmake
  DESTINATION share/${PROJECT_NAME}/cmake)

install(FILES package.xml
  DESTINATION share/${PROJECT_NAME})

if(BUILD_TESTING)
  find_package(ament_cmake_pytest REQUIRED)
  ament_add_pytest_test(test_ament_nodl_install test/test_ament_nodl_install.py)
  ament_add_pytest_test(test_register_executable test/test_register_executable.py)
  ament_add_pytest_test(test_register_component test/test_register_component.py)
  ament_add_pytest_test(test_macro_rejection test/test_macro_rejection.py)
endif()

ament_package(CONFIG_EXTRAS "ament_nodl-extras.cmake.in")
