# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
cmake_minimum_required(VERSION 3.22)
project(test_ament_nodl)

find_package(ament_cmake REQUIRED)
find_package(ament_nodl REQUIRED)

# Default PACKAGE resolves to ${PROJECT_NAME}.
ament_nodl_register_node(basic_node FILE test/fixtures/basic_node.nodl.yaml)

# Explicit PACKAGE override; the resource key and install destination both pick it up.
ament_nodl_register_node(custom_exe
  FILE test/fixtures/alt_pkg_node.nodl.yaml
  PACKAGE custom_pkg)

# Non-yaml frontend; the macro is extension-agnostic and just copies bytes.
ament_nodl_register_node(json_node FILE test/fixtures/json_node.nodl.json)

if(BUILD_TESTING)
  find_package(ament_cmake_pytest REQUIRED)
  ament_add_pytest_test(register_node_tests test/test_register_node.py)
endif()

ament_package()
