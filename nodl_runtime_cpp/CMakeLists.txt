# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
cmake_minimum_required(VERSION 3.22)
project(nodl_runtime_cpp)

if(NOT CMAKE_CXX_STANDARD)
  set(CMAKE_CXX_STANDARD 17)
endif()

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(rclcpp_action REQUIRED)
find_package(rclcpp_lifecycle REQUIRED)

add_library(${PROJECT_NAME} INTERFACE)
target_include_directories(${PROJECT_NAME} INTERFACE
  "$<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>"
  "$<INSTALL_INTERFACE:include/${PROJECT_NAME}>")
target_link_libraries(${PROJECT_NAME} INTERFACE
  rclcpp::rclcpp
  rclcpp_action::rclcpp_action
  rclcpp_lifecycle::rclcpp_lifecycle)

install(DIRECTORY include/ DESTINATION include/${PROJECT_NAME})
install(TARGETS ${PROJECT_NAME} EXPORT export_${PROJECT_NAME})

if(BUILD_TESTING)
  find_package(ament_cmake_gtest REQUIRED)
  find_package(example_interfaces REQUIRED)
  find_package(lifecycle_msgs REQUIRED)
  find_package(std_msgs REQUIRED)

  ament_add_gtest(test_lifecycle_node test/test_lifecycle_node.cpp TIMEOUT 60)
  target_link_libraries(test_lifecycle_node
    ${PROJECT_NAME}
    ${lifecycle_msgs_TARGETS}
    ${std_msgs_TARGETS})

  ament_add_gtest(test_active_only_entities test/test_active_only_entities.cpp TIMEOUT 60)
  target_link_libraries(test_active_only_entities
    ${PROJECT_NAME}
    ${example_interfaces_TARGETS})

  # The documentation example is compiled but not installed or run.
  add_executable(lifecycle_node_example doc/examples/lifecycle_node.cpp)
  target_link_libraries(lifecycle_node_example
    ${PROJECT_NAME}
    ${example_interfaces_TARGETS}
    ${std_msgs_TARGETS})
endif()

ament_export_targets(export_${PROJECT_NAME})
ament_export_dependencies(rclcpp rclcpp_action rclcpp_lifecycle)
ament_package()
