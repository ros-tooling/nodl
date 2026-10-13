# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
cmake_minimum_required(VERSION 3.22)
project(nodl_tutorial_basics)

find_package(ament_cmake REQUIRED)
find_package(ament_nodl REQUIRED)
find_package(nodl_generator_cpp REQUIRED)

ament_nodl_register(talker FILE nodl/talker.nodl.yaml)
nodl_generate_cpp(talker_base RESOURCE_NAME talker_cpp nodl/talker_codegen.nodl.yaml)

add_executable(talker_cpp cpp/talker.cpp)
target_link_libraries(talker_cpp PRIVATE talker_base)

install(TARGETS talker_cpp
  DESTINATION lib/${PROJECT_NAME})

find_package(nodl_generator_py REQUIRED)

# The contract is already registered as talker.
nodl_generate_py(talker_py_base nodl/talker.nodl.yaml NO_INDEX)

install(PROGRAMS python/talker.py
  DESTINATION lib/${PROJECT_NAME}
  RENAME talker)

if(BUILD_TESTING)
  nodl_add_conformance_test(talker_cpp_conformance
    EXECUTABLE talker_cpp
    NODL_FILE nodl/talker.nodl.yaml)
  nodl_add_conformance_test(talker_py_conformance
    EXECUTABLE talker
    NODL_FILE nodl/talker.nodl.yaml)
  # Fast DDS on Humble and Jazzy does not expose history/depth over discovery.
  set_property(TEST talker_cpp_conformance talker_py_conformance APPEND PROPERTY
    ENVIRONMENT "RMW_IMPLEMENTATION=rmw_cyclonedds_cpp")

  find_package(ament_cmake_pytest REQUIRED)
  ament_add_pytest_test(tutorial_registration_tests test/test_registration.py)
  ament_add_pytest_test(tutorial_runtime_tests test/test_runtime.py TIMEOUT 90)
endif()

ament_package()
