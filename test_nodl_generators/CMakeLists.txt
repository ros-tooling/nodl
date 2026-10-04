# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
cmake_minimum_required(VERSION 3.22)
project(test_nodl_generators)

find_package(ament_cmake REQUIRED)
find_package(nodl_generator_cpp REQUIRED)
find_package(nodl_generator_py REQUIRED)

# A macro, because exported targets cannot be created inside a function.
macro(add_cpp_fixture fixture target)
  nodl_generate_cpp(${target} ${ARGN} ${fixture}/cpp/node.nodl.yaml)
  add_executable(test_cpp_${fixture} ${fixture}/cpp/test_node.cpp)
  target_link_libraries(test_cpp_${fixture} PRIVATE ${target})
endmacro()

# The target prefix keeps these distinct from the Python generator fixtures.
add_cpp_fixture(minimal cpp_minimal_node_base SHARED)
add_cpp_fixture(pub_sub cpp_pub_sub_node_base)
add_cpp_fixture(services cpp_services_node_base)
add_cpp_fixture(parameters cpp_params_node_base)
add_cpp_fixture(kitchen_sink cpp_kitchen_sink_node_base NO_EXPORT)
add_cpp_fixture(lifecycle cpp_lifecycle_node_base)
add_cpp_fixture(namespace cpp_namespace_node_base)

# A STATIC base linked into a SHARED library needs position-independent code.
nodl_generate_cpp(cpp_minimal_static_node_base STATIC minimal/cpp/node.nodl.yaml)
add_library(cpp_minimal_static_plugin SHARED minimal/cpp/test_static_plugin.cpp)
target_link_libraries(cpp_minimal_static_plugin PRIVATE cpp_minimal_static_node_base)

if(BUILD_TESTING)
  find_package(ament_cmake_pytest REQUIRED)

  # Checks which fixtures are installed and exported.
  # It reads the install manifest, so files left by earlier builds in the install prefix do not matter.
  ament_add_pytest_test(test_install_space test_install_space.py
    ENV INSTALL_MANIFEST=${CMAKE_BINARY_DIR}/install_manifest.txt
  )

  function(add_python_fixture fixture target)
    nodl_generate_py(${target} ${fixture}/py/node.nodl.yaml)
    set(pythonpath "${CMAKE_CURRENT_BINARY_DIR}/nodl_generated/${target}")
    string(APPEND pythonpath ":${CMAKE_CURRENT_SOURCE_DIR}/${fixture}/py")
    ament_add_pytest_test(
      test_${fixture} ${fixture}/py/test_node.py
      APPEND_ENV PYTHONPATH=${pythonpath}
    )
  endfunction()

  add_python_fixture(minimal minimal_node_base)
  add_python_fixture(pub_sub pubsub_node_base)
  add_python_fixture(services services_node_base)
  add_python_fixture(actions actions_node_base)
  add_python_fixture(parameters parameters_node_base)
  add_python_fixture(kitchen_sink kitchen_sink_node_base)
  add_python_fixture(lifecycle lifecycle_node_base)
endif()

ament_package()
