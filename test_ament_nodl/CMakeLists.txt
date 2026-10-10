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
ament_nodl_register(custom_resource
  FILE test/fixtures/alt_pkg_node.nodl.yaml
  PACKAGE custom_pkg)

# Non-yaml frontend. Make sure the macro is extension-agnostic.
ament_nodl_register(json_node FILE test/fixtures/json_node.nodl.json)

# Registration from a subdirectory.
# The root document registered here includes it, so rewriting must see registrations from every directory.
ament_nodl_register(root_includes_subdir_node FILE test/fixtures/root_includes_subdir_node.nodl.yaml)
add_subdirectory(test/fixtures/subdir)

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

  # The fixture node refuses to start unless it is given its required `limit` and `mode` parameters.
  # rcl reads `1_000` as a string and PyYAML as an integer, so `mode` only starts when items reach the node as `-p` arguments.
  nodl_add_conformance_test(conformance_fixture
    EXECUTABLE conformance_fixture_node
    NODL_FILE test/fixtures/conformance_fixture.nodl.yaml
    NODE_NAME fixture
    NODE_NAMESPACE /conformance
    TIMEOUT 15
    PARAMETERS limit:=5 mode:=1_000
  )

  nodl_add_conformance_test(conformance_fixture_parameters_file
    EXECUTABLE conformance_fixture_node
    NODL_FILE test/fixtures/conformance_fixture.nodl.yaml
    NODE_NAME fixture_file
    NODE_NAMESPACE /conformance
    TIMEOUT 15
    PARAMETERS_FILE test/fixtures/conformance_fixture_parameters.yaml
  )

  # The file sets values the node rejects, so the test passes only if the inline items win.
  nodl_add_conformance_test(conformance_fixture_parameters_override
    EXECUTABLE conformance_fixture_node
    NODL_FILE test/fixtures/conformance_fixture.nodl.yaml
    NODE_NAME fixture_override
    NODE_NAMESPACE /conformance
    TIMEOUT 15
    PARAMETERS_FILE test/fixtures/conformance_fixture_wrong_parameters.yaml
    PARAMETERS limit:=5 mode:=1_000
  )

  # NODE_NAME defaults to the test name.
  nodl_add_conformance_test(conformance_fixture_default_name
    EXECUTABLE conformance_fixture_node
    NODL_FILE test/fixtures/conformance_fixture.nodl.yaml
    NODE_NAMESPACE /conformance
    PARAMETERS limit:=5 mode:=1_000
  )

  ament_add_pytest_test(test_register_node test/test_register_node.py)
  ament_add_pytest_test(test_macro_rejection test/test_macro_rejection.py)
  ament_add_pytest_test(test_superbuild test/test_superbuild.py)
  ament_add_pytest_test(test_composition test/test_composition.py)
  ament_add_pytest_test(test_pyright test/test_pyright.py)
endif()

ament_package()
