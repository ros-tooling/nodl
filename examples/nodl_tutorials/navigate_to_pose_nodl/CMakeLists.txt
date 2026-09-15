# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
cmake_minimum_required(VERSION 3.22)
project(navigate_to_pose_nodl)

find_package(ament_cmake REQUIRED)
find_package(ament_cmake_python REQUIRED)
find_package(ament_nodl REQUIRED)

ament_nodl_register(navigate_to_pose_client FILE nodl/navigate_to_pose_client.nodl.yaml)

find_package(nodl_generator_cpp REQUIRED)
nodl_generate_cpp(navigate_to_pose_client_base nodl/navigate_to_pose_client_codegen.nodl.yaml)

add_executable(navigate_to_pose_client_nodl_cpp
  src/navigate_to_pose_client_nodl.cpp
  src/navigation.cpp)
target_include_directories(navigate_to_pose_client_nodl_cpp PRIVATE src)
target_link_libraries(navigate_to_pose_client_nodl_cpp PRIVATE navigate_to_pose_client_base)
install(TARGETS navigate_to_pose_client_nodl_cpp
  DESTINATION lib/${PROJECT_NAME})

find_package(nodl_generator_py REQUIRED)
nodl_generate_py(navigate_to_pose_client_py_base nodl/navigate_to_pose_client.nodl.yaml)

ament_python_install_package(${PROJECT_NAME})
install(PROGRAMS
  ${PROJECT_NAME}/navigate_to_pose_client_nodl.py
  DESTINATION lib/${PROJECT_NAME}
  RENAME navigate_to_pose_client_nodl)

if(BUILD_TESTING)
  find_package(ament_cmake_pytest REQUIRED)
  find_package(launch_testing_ament_cmake REQUIRED)

  # Compile the documented conventional C++ client so the before example cannot drift.
  add_executable(navigate_to_pose_client_cpp
    src/navigate_to_pose_client.cpp
    src/navigation.cpp)
  target_include_directories(navigate_to_pose_client_cpp PRIVATE src)
  target_link_libraries(navigate_to_pose_client_cpp PRIVATE
    ${nav2_msgs_TARGETS}
    rclcpp::rclcpp
    rclcpp_action::rclcpp_action)

  ament_add_pytest_test(tutorial_tests test/test_clients.py TIMEOUT 90)
  nodl_add_conformance_test(navigate_to_pose_client_nodl_conformance_cpp
    EXECUTABLE navigate_to_pose_client_nodl_cpp
    NODL_FILE nodl/navigate_to_pose_client.nodl.yaml
    NODE_NAME navigate_to_pose_client
    TIMEOUT 20)
  nodl_add_conformance_test(navigate_to_pose_client_nodl_conformance_py
    EXECUTABLE navigate_to_pose_client_nodl
    NODL_FILE nodl/navigate_to_pose_client.nodl.yaml
    NODE_NAME navigate_to_pose_client_py
    TIMEOUT 20)
endif()

ament_package()
