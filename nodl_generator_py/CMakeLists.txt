# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
cmake_minimum_required(VERSION 3.16)
project(nodl_generator_py)

find_package(ament_cmake REQUIRED)
find_package(ament_cmake_python REQUIRED)

# Importable generator core used by the CLI and tests.
ament_python_install_package(${PROJECT_NAME})
ament_get_python_install_dir(PYTHON_INSTALL_DIR)

install(
  DIRECTORY nodl_generator_py/templates
  DESTINATION "${PYTHON_INSTALL_DIR}/${PROJECT_NAME}"
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
