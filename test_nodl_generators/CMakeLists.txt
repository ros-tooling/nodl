# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
cmake_minimum_required(VERSION 3.22)
project(test_nodl_generators)

find_package(ament_cmake REQUIRED)
# Libraries without a type keyword are SHARED.
option(BUILD_SHARED_LIBS "Build shared libraries" ON)
find_package(nodl_generator_cpp REQUIRED)
find_package(nodl_generator_py REQUIRED)

# A macro, because exported targets cannot be created inside a function.
macro(add_cpp_fixture fixture target)
  nodl_generate_cpp(${target} ${ARGN} ${fixture}/cpp/node.nodl.yaml)
  add_executable(test_cpp_${fixture} ${fixture}/cpp/test_node.cpp)
  target_link_libraries(test_cpp_${fixture} PRIVATE ${target})
endmacro()

# The target prefix keeps these distinct from the Python generator fixtures.
# Each fixture document is registered with the ament index under its target name.
# The pub_sub and namespace fixtures override it with RESOURCE_NAME.
add_cpp_fixture(minimal cpp_minimal_node_base SHARED EXPORT)
add_cpp_fixture(pub_sub cpp_pub_sub_node_base EXPORT RESOURCE_NAME cpp_pub_sub_node)
add_cpp_fixture(services cpp_services_node_base EXPORT)
add_cpp_fixture(parameters cpp_params_node_base EXPORT)
add_cpp_fixture(lifecycle cpp_lifecycle_node_base EXPORT)

# Without EXPORT, a SHARED library is installed for runtime only, with no headers.
add_cpp_fixture(kitchen_sink cpp_kitchen_sink_node_base)
add_cpp_fixture(namespace cpp_namespace_node_base RESOURCE_NAME cpp_namespace_node)

# The STATIC and BUILD_SHARED_LIBS fixtures reuse the minimal document, which is already registered,
# and a document file can be registered only once per package.
# A STATIC library is exported like a SHARED one.
# Linked into a SHARED library, it needs position-independent code.
nodl_generate_cpp(cpp_minimal_static_node_base STATIC EXPORT NO_INDEX minimal/cpp/node.nodl.yaml)
add_library(cpp_minimal_static_plugin SHARED minimal/cpp/test_static_plugin.cpp)
target_link_libraries(cpp_minimal_static_plugin PRIVATE cpp_minimal_static_node_base)

# A STATIC library without EXPORT is not installed at all.
nodl_generate_cpp(cpp_private_static_node_base STATIC NO_INDEX minimal/cpp/node.nodl.yaml)

# Without a type keyword the library follows BUILD_SHARED_LIBS.
# With it OFF, the library is STATIC and so is not installed without EXPORT.
# SHARED overrides it.
if(DEFINED BUILD_SHARED_LIBS)
  set(_saved_build_shared_libs "${BUILD_SHARED_LIBS}")
endif()
set(BUILD_SHARED_LIBS OFF)
nodl_generate_cpp(cpp_off_default_node_base NO_INDEX minimal/cpp/node.nodl.yaml)
nodl_generate_cpp(cpp_off_shared_node_base SHARED NO_INDEX minimal/cpp/node.nodl.yaml)
if(DEFINED _saved_build_shared_libs)
  set(BUILD_SHARED_LIBS "${_saved_build_shared_libs}")
else()
  unset(BUILD_SHARED_LIBS)
endif()

if(BUILD_TESTING)
  find_package(ament_cmake_pytest REQUIRED)

  # These tests read the install manifests in the build directory, so files left by earlier builds in the install prefix do not matter.
  # Checks which fixtures are installed and exported.
  ament_add_pytest_test(test_install_space test_install_space.py
    ENV BUILD_DIR=${CMAKE_BINARY_DIR}
  )

  # Checks which fixtures are registered with the ament index.
  ament_add_pytest_test(test_ament_index test_ament_index.py
    ENV BUILD_DIR=${CMAKE_BINARY_DIR}
  )

  # Each Python fixture document is registered with the ament index under its target name.
  # The pub_sub fixture overrides it with RESOURCE_NAME, and the services fixture passes NO_INDEX.
  function(add_python_fixture fixture target)
    nodl_generate_py(${target} ${fixture}/py/node.nodl.yaml ${ARGN})
    set(pythonpath "${CMAKE_CURRENT_BINARY_DIR}/nodl_generated/${target}")
    string(APPEND pythonpath ":${CMAKE_CURRENT_SOURCE_DIR}/${fixture}/py")
    ament_add_pytest_test(
      test_${fixture} ${fixture}/py/test_node.py
      APPEND_ENV PYTHONPATH=${pythonpath}
    )
  endfunction()

  add_python_fixture(minimal minimal_node_base)
  add_python_fixture(pub_sub pubsub_node_base RESOURCE_NAME pubsub_node)
  add_python_fixture(services services_node_base NO_INDEX)
  add_python_fixture(actions actions_node_base)
  add_python_fixture(parameters parameters_node_base)
  add_python_fixture(kitchen_sink kitchen_sink_node_base)
  add_python_fixture(lifecycle lifecycle_node_base)
endif()

ament_package()
