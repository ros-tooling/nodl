# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
cmake_minimum_required(VERSION 3.22)
project(test_nodl_generators)

find_package(ament_cmake REQUIRED)
find_package(nodl_generator_cpp REQUIRED)
find_package(nodl_generator_py REQUIRED)

# Generate and compile C++ base-node fixtures.
# The target prefix keeps these distinct from the Python generator fixtures.
nodl_generate_cpp(cpp_minimal_node_base cpp/nodl/minimal_node.nodl.yaml)
nodl_generate_cpp(cpp_pub_sub_node_base cpp/nodl/pub_sub_node.nodl.yaml)
nodl_generate_cpp(cpp_services_node_base cpp/nodl/services_node.nodl.yaml)
nodl_generate_cpp(cpp_params_node_base cpp/nodl/params_node.nodl.yaml)
nodl_generate_cpp(cpp_kitchen_sink_node_base cpp/nodl/kitchen_sink_node.nodl.yaml)
nodl_generate_cpp(cpp_lifecycle_node_base cpp/nodl/lifecycle_node.nodl.yaml)

add_executable(test_minimal_node cpp/src/test_minimal_node.cpp)
target_link_libraries(test_minimal_node PRIVATE cpp_minimal_node_base)

add_executable(test_pub_sub_node cpp/src/test_pub_sub_node.cpp)
target_link_libraries(test_pub_sub_node PRIVATE cpp_pub_sub_node_base)

add_executable(test_services_node cpp/src/test_services_node.cpp)
target_link_libraries(test_services_node PRIVATE cpp_services_node_base)

add_executable(test_params_node cpp/src/test_params_node.cpp)
target_link_libraries(test_params_node PRIVATE cpp_params_node_base)

add_executable(test_kitchen_sink_node cpp/src/test_kitchen_sink_node.cpp)
target_link_libraries(test_kitchen_sink_node PRIVATE cpp_kitchen_sink_node_base)

add_executable(test_lifecycle_node cpp/src/test_lifecycle_node.cpp)
target_link_libraries(test_lifecycle_node PRIVATE cpp_lifecycle_node_base)

if(BUILD_TESTING)
  find_package(ament_cmake_pytest REQUIRED)

  function(add_python_fixture fixture target)
    nodl_generate_py(${target} ${fixture}/nodl/node.nodl.yaml)
    set(pythonpath "${CMAKE_CURRENT_BINARY_DIR}/nodl_generated/${target}")
    string(APPEND pythonpath ":${CMAKE_CURRENT_SOURCE_DIR}/${fixture}/python")
    ament_add_pytest_test(
      test_${fixture} ${fixture}/python/test_node.py
      APPEND_ENV PYTHONPATH=${pythonpath}
    )
  endfunction()

  add_python_fixture(pub_sub pubsub_node_base)
  add_python_fixture(services services_node_base)
  add_python_fixture(actions actions_node_base)
  add_python_fixture(parameters parameters_node_base)
  add_python_fixture(kitchen_sink kitchen_sink_node_base)
endif()

ament_package()
