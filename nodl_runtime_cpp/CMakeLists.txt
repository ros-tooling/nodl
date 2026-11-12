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

find_package(ament_cmake_auto REQUIRED)
ament_auto_find_build_dependencies()

add_library(${PROJECT_NAME} INTERFACE)
target_include_directories(${PROJECT_NAME} INTERFACE
  "$<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>"
  "$<INSTALL_INTERFACE:include/${PROJECT_NAME}>"
)
target_link_libraries(${PROJECT_NAME} INTERFACE
  lifecycle_msgs::lifecycle_msgs
  rclcpp::rclcpp
  rclcpp_lifecycle::rclcpp_lifecycle
)

if(BUILD_TESTING)
  ament_auto_find_test_dependencies()

  ament_add_gtest(test_lifecycle_node test/test_lifecycle_node.cpp TIMEOUT 60)
  target_link_libraries(test_lifecycle_node
    ${PROJECT_NAME}
    std_msgs::std_msgs
  )

  # The documentation example is compiled but not installed or run.
  add_executable(lifecycle_node_example doc/examples/lifecycle_node.cpp)
  target_link_libraries(lifecycle_node_example ${PROJECT_NAME} std_msgs::std_msgs)
endif()


install(DIRECTORY include/ DESTINATION include/${PROJECT_NAME})
install(TARGETS ${PROJECT_NAME} EXPORT export_${PROJECT_NAME})

ament_export_targets(export_${PROJECT_NAME})
ament_export_dependencies(lifecycle_msgs rclcpp rclcpp_action rclcpp_lifecycle)
ament_package()
