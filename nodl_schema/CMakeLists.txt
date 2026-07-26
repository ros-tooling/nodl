# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
cmake_minimum_required(VERSION 3.22)
project(nodl_schema)

find_package(ament_cmake REQUIRED)
find_package(ament_cmake_python REQUIRED)

# --- Python package ---
ament_python_install_package(nodl_schema)

# Install schema files alongside the Python package so they are accessible
# both via importlib.resources and from the ament share directory.
install(FILES
  nodl_schema/schemas/nodl.schema.yaml
  nodl_schema/schemas/parameter.schema.yaml
  DESTINATION share/${PROJECT_NAME}/schemas)

# --- CMake macros (ament_nodl_*) ---
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
  ament_add_pytest_test(test_schema test/test_schema.py)
  ament_add_pytest_test(test_validator_cli test/test_validator_cli.py)
  ament_add_pytest_test(test_ament_nodl_install test/test_ament_nodl_install.py)
  ament_add_pytest_test(test_register_executable test/test_register_executable.py)
  ament_add_pytest_test(test_register_component test/test_register_component.py)
  ament_add_pytest_test(test_macro_rejection test/test_macro_rejection.py)
  ament_add_pytest_test(test_integration test/test_integration.py)
endif()

ament_package(CONFIG_EXTRAS "nodl_schema-extras.cmake.in")
