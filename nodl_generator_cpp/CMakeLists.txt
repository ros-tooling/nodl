# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
cmake_minimum_required(VERSION 3.22)
project(nodl_generator_cpp)

find_package(ament_cmake REQUIRED)
find_package(ament_cmake_python REQUIRED)

ament_python_install_package(${PROJECT_NAME})

install(
  DIRECTORY cmake
  DESTINATION share/${PROJECT_NAME}
)

if(BUILD_TESTING)
  # Linting/formatting is handled repo-wide by pre-commit (polymath_code_standard),
  # not by ament_lint_auto -- matching the other packages in this workspace.
  find_package(ament_cmake_pytest REQUIRED)

  # The unit tests are pure Python (generator pipeline, provenance, schema);
  # they exercise the installed nodl_generator_cpp package with no C++ build.
  ament_add_pytest_test(nodl_generator_cpp_tests test
    TIMEOUT 120
  )
endif()

ament_package(CONFIG_EXTRAS "nodl_generate_cpp-extras.cmake.in")
