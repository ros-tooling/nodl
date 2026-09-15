# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
cmake_minimum_required(VERSION 3.16)
project(test_nodl_generators)

find_package(ament_cmake REQUIRED)
find_package(nodl_generator_py REQUIRED)

if(BUILD_TESTING)
  find_package(ament_cmake_pytest REQUIRED)

  function(add_python_fixture fixture target)
    nodl_generate_py(${target} ${fixture}/nodl/node.nodl.yaml)
    set(pythonpath "${CMAKE_CURRENT_BINARY_DIR}/nodl_generated/${target}")
    string(APPEND pythonpath ":${CMAKE_CURRENT_SOURCE_DIR}/${fixture}/python")
    ament_add_pytest_test(
      test_${fixture} ${fixture}/python/test_node.py
      APPEND_ENV PYTHONPATH=${pythonpath}
    )
  endfunction()

  add_python_fixture(pub_sub pubsub_node_base)
  add_python_fixture(services services_node_base)
  add_python_fixture(actions actions_node_base)
  add_python_fixture(parameters parameters_node_base)
  add_python_fixture(kitchen_sink kitchen_sink_node_base)
  add_python_fixture(lifecycle lifecycle_node_base)
endif()

ament_package()
