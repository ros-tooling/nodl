# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
cmake_minimum_required(VERSION 3.22)
project(nodl_tutorial_dummy_robot)

find_package(ament_cmake REQUIRED)
find_package(ament_nodl REQUIRED)
find_package(nodl_generator_cpp REQUIRED)

ament_nodl_register(dummy_laser FILE nodl/dummy_laser.nodl.yaml)
nodl_generate_cpp(dummy_laser nodl/dummy_laser_codegen.nodl.yaml)

add_executable(dummy_laser_nodl src/dummy_laser_nodl.cpp)
target_include_directories(dummy_laser_nodl PRIVATE include)
target_link_libraries(dummy_laser_nodl PRIVATE dummy_laser)

add_executable(dummy_laser_regression src/dummy_laser_regression.cpp)
target_include_directories(dummy_laser_regression PRIVATE include)
target_link_libraries(dummy_laser_regression PRIVATE ${rclcpp_TARGETS} ${sensor_msgs_TARGETS})

install(TARGETS dummy_laser_nodl dummy_laser_regression
  DESTINATION lib/${PROJECT_NAME})
install(DIRECTORY launch DESTINATION share/${PROJECT_NAME})
install(DIRECTORY rviz DESTINATION share/${PROJECT_NAME})

if(BUILD_TESTING)
  find_package(ament_cmake_pytest REQUIRED)
  ament_add_pytest_test(tutorial_registration_tests test/test_registration.py)
  ament_add_pytest_test(tutorial_runtime_tests test/test_runtime.py TIMEOUT 90)
endif()

ament_package()
