# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
cmake_minimum_required(VERSION 3.22)
project(nodl_tutorial_lifecycle_migration)

find_package(ament_cmake REQUIRED)
find_package(ament_nodl REQUIRED)
find_package(nodl_generator_cpp REQUIRED)
find_package(nodl_generator_py REQUIRED)
find_package(rclcpp REQUIRED)
find_package(rclcpp_lifecycle REQUIRED)
find_package(std_msgs REQUIRED)
find_package(std_srvs REQUIRED)

# The handwritten nodes derive the lifecycle node of rclcpp and rclpy directly.
add_executable(handwritten_greeter_cpp cpp/handwritten_greeter.cpp)
target_link_libraries(handwritten_greeter_cpp PRIVATE
  rclcpp::rclcpp
  rclcpp_lifecycle::rclcpp_lifecycle
  std_msgs::std_msgs
  std_srvs::std_srvs)

install(PROGRAMS python/handwritten_greeter.py
  DESTINATION lib/${PROJECT_NAME}
  RENAME handwritten_greeter_py)

# The migrated nodes derive the generated base of the same interface.
nodl_generate_cpp(greeter_base RESOURCE_NAME greeter nodl/greeter.nodl.yaml)

add_executable(greeter_cpp cpp/greeter.cpp)
target_link_libraries(greeter_cpp PRIVATE greeter_base)

# The document is already registered as greeter.
nodl_generate_py(greeter_py_base nodl/greeter.nodl.yaml NO_INDEX)

install(PROGRAMS python/greeter.py
  DESTINATION lib/${PROJECT_NAME}
  RENAME greeter_py)

install(TARGETS handwritten_greeter_cpp greeter_cpp
  DESTINATION lib/${PROJECT_NAME})

if(BUILD_TESTING)
  # A lifecycle node is configured and activated before the comparison.
  nodl_add_conformance_test(greeter_cpp_conformance
    EXECUTABLE greeter_cpp
    NODE_NAME greeter
    NODL_FILE nodl/greeter.nodl.yaml)
  nodl_add_conformance_test(greeter_py_conformance
    EXECUTABLE greeter_py
    NODE_NAME greeter_py
    NODL_FILE nodl/greeter.nodl.yaml)
  # Fast DDS on Humble and Jazzy does not expose history/depth over discovery.
  set_property(TEST greeter_cpp_conformance greeter_py_conformance APPEND PROPERTY
    ENVIRONMENT "RMW_IMPLEMENTATION=rmw_cyclonedds_cpp")

  find_package(ament_cmake_pytest REQUIRED)
  ament_add_pytest_test(lifecycle_migration_tests test/test_greeters.py TIMEOUT 180)
endif()

ament_package()
