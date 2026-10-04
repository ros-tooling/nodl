# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
cmake_minimum_required(VERSION 3.22)
project(test_nodl_generators_downstream)

find_package(ament_cmake REQUIRED)
# Resolves the exported targets and, through them, the packages their interfaces link.
find_package(test_nodl_generators REQUIRED)

# A target created with NO_EXPORT is not visible downstream.
if(TARGET test_nodl_generators::cpp_kitchen_sink_node_base)
  message(FATAL_ERROR "A NO_EXPORT target was exported")
endif()

if(BUILD_TESTING)
  find_package(ament_cmake_gtest REQUIRED)

  ament_add_gtest(test_subclass_exported_base test/test_subclass_exported_base.cpp)
  target_link_libraries(test_subclass_exported_base
    test_nodl_generators::cpp_minimal_node_base
    test_nodl_generators::cpp_params_node_base
  )
endif()

ament_package()
