# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0

cmake_minimum_required(VERSION 3.8)
project(nodl_observe)

if(NOT CMAKE_CXX_STANDARD)
  set(CMAKE_CXX_STANDARD 17)
endif()

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic -Werror=switch)
  add_link_options("-Wl,--no-undefined")
endif()

find_package(ament_cmake_auto REQUIRED)
ament_auto_find_build_dependencies()

find_package(CLI11 REQUIRED)

if(NOT DEFINED ENV{ROS_DISTRO})
  message(FATAL_ERROR "ROS_DISTRO environment variable not set")
else()
  string(TOUPPER "$ENV{ROS_DISTRO}" ROS_DISTRO)
  message(STATUS "Detected ROS 2 distro ${ROS_DISTRO} from environment")
  add_compile_definitions("ROS2_${ROS_DISTRO}")
endif()

# Core library (pure builders + graph orchestration; no node ownership).
ament_auto_add_library(${PROJECT_NAME} SHARED
  src/qos.cpp
  src/endpoints.cpp
  src/actions.cpp
  src/parameters.cpp
  src/observe.cpp
)
target_include_directories(${PROJECT_NAME} PUBLIC
  "$<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>"
  "$<INSTALL_INTERFACE:include>")

# `observe` executable: thin node wrapper + latched publish.
ament_auto_add_executable(observe
  src/observe_main.cpp
)
target_link_libraries(observe ${PROJECT_NAME} CLI11::CLI11)

# ament_auto_add_library / _executable already install and export their targets
# via ament_auto_package() below (lib -> lib, executable -> lib/${PROJECT_NAME});
# only the public headers need an explicit install.
install(
  DIRECTORY include/
  DESTINATION include
)

if(BUILD_TESTING)
  # Linting/formatting is handled repo-wide by pre-commit (polymath_code_standard),
  # not by ament_lint_auto -- matching the other packages in this workspace.
  find_package(ament_cmake_gtest REQUIRED)

  ament_add_gtest(test_qos test/test_qos.cpp)
  target_link_libraries(test_qos ${PROJECT_NAME})

  ament_add_gtest(test_endpoints test/test_endpoints.cpp)
  target_link_libraries(test_endpoints ${PROJECT_NAME})

  ament_add_gtest(test_actions test/test_actions.cpp)
  target_link_libraries(test_actions ${PROJECT_NAME})

  ament_add_gtest(test_parameters test/test_parameters.cpp)
  target_link_libraries(test_parameters ${PROJECT_NAME})

  # Degradation path for collect_parameters -- needs a live rclcpp context.
  ament_add_gtest(test_collect_parameters test/test_collect_parameters.cpp)
  target_link_libraries(test_collect_parameters ${PROJECT_NAME})

  # Register the RMW-sensitive integration test once per RMW via
  # call_for_each_rmw_implementation (a macro(), not function(); see
  # rcl/test/CMakeLists.txt). ctest -> test_observe_integration__<rmw>.
  find_package(ament_cmake_pytest REQUIRED)
  find_package(rmw_implementation_cmake REQUIRED)

  # The integration test needs `mcap-ros2-support` test dependency.
  set(_observe_integration_skip "")
  if(NOT "$ENV{ENABLE_PIP_TEST_DEPENDS}" STREQUAL "1")
    set(_observe_integration_skip "SKIP_TEST")
  endif()

  macro(observe_integration_test_for_rmw)
    ament_add_pytest_test(
      "test_observe_integration${target_suffix}"
      test/test_observe_integration.py
      ENV RMW_IMPLEMENTATION=${rmw_implementation}
      TIMEOUT 180
      ${_observe_integration_skip}
    )
  endmacro()

  call_for_each_rmw_implementation(observe_integration_test_for_rmw)
endif()

ament_auto_package()
