# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
cmake_minimum_required(VERSION 3.22)
project(test_nodl_generator_cpp)

find_package(ament_cmake REQUIRED)
find_package(nodl_generator_cpp REQUIRED)

# --- Generate base-node libraries from NoDL documents ---

nodl_generate_cpp(minimal_node_base       nodl/minimal_node.nodl.yaml)
nodl_generate_cpp(pub_sub_node_base       nodl/pub_sub_node.nodl.yaml)
nodl_generate_cpp(services_node_base      nodl/services_node.nodl.yaml)
nodl_generate_cpp(params_node_base        nodl/params_node.nodl.yaml)
nodl_generate_cpp(kitchen_sink_node_base  nodl/kitchen_sink_node.nodl.yaml)
nodl_generate_cpp(lifecycle_node_base     nodl/lifecycle_node.nodl.yaml)

# --- Build tests — if these compile and link, the generator works ---

add_executable(test_minimal_node      src/test_minimal_node.cpp)
target_link_libraries(test_minimal_node PRIVATE minimal_node_base)

add_executable(test_pub_sub_node      src/test_pub_sub_node.cpp)
target_link_libraries(test_pub_sub_node PRIVATE pub_sub_node_base)

add_executable(test_services_node     src/test_services_node.cpp)
target_link_libraries(test_services_node PRIVATE services_node_base)

add_executable(test_params_node       src/test_params_node.cpp)
target_link_libraries(test_params_node PRIVATE params_node_base)

add_executable(test_kitchen_sink_node src/test_kitchen_sink_node.cpp)
target_link_libraries(test_kitchen_sink_node PRIVATE kitchen_sink_node_base)

add_executable(test_lifecycle_node    src/test_lifecycle_node.cpp)
target_link_libraries(test_lifecycle_node PRIVATE lifecycle_node_base)

ament_package()
