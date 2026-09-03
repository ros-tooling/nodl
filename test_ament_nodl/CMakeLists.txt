# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
cmake_minimum_required(VERSION 3.22)
project(test_ament_nodl)

find_package(ament_cmake REQUIRED)
find_package(ament_nodl REQUIRED)

# Registered before basic_node on purpose: it references basic_node,
# and we want to test regritration-order-independent resolution
ament_nodl_register(composed_node FILE test/fixtures/composed_node.nodl.yaml)

# Default PACKAGE resolves to ${PROJECT_NAME}.
ament_nodl_register(basic_node FILE test/fixtures/basic_node.nodl.yaml)

# Explicit PACKAGE override. The resource key and install destination both pick it up.
ament_nodl_register(custom_exe
  FILE test/fixtures/alt_pkg_node.nodl.yaml
  PACKAGE custom_pkg)

# Non-yaml frontend. Make sure the macro is extension-agnostic.
ament_nodl_register(json_node FILE test/fixtures/json_node.nodl.json)

if(BUILD_TESTING)
  find_package(ament_cmake_pytest REQUIRED)
  find_package(rcl_interfaces REQUIRED)
  find_package(rclcpp REQUIRED)
  find_package(std_msgs REQUIRED)
  find_package(std_srvs REQUIRED)

  add_executable(conformance_fixture_node src/conformance_fixture_node.cpp)
  target_link_libraries(
    conformance_fixture_node
    PRIVATE
      rclcpp::rclcpp
      ${rcl_interfaces_TARGETS}
      ${std_msgs_TARGETS}
      ${std_srvs_TARGETS})
  install(TARGETS conformance_fixture_node DESTINATION lib/${PROJECT_NAME})

  nodl_add_conformance_test(conformance_fixture
    EXECUTABLE conformance_fixture_node
    NODL_FILE test/fixtures/conformance_fixture.nodl.yaml
    NODE_NAME fixture
    NODE_NAMESPACE /conformance
    TIMEOUT 15
  )

  ament_add_pytest_test(test_register_node test/test_register_node.py)
  ament_add_pytest_test(test_macro_rejection test/test_macro_rejection.py)
  ament_add_pytest_test(test_composition test/test_composition.py)
  ament_add_pytest_test(test_pyright test/test_pyright.py)
endif()

ament_package()
