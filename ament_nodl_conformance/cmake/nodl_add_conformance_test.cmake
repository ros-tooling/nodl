# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
#[=[
Register a launch test that compares one executable with one NoDL document.

Required arguments are EXECUTABLE, NODL_FILE, and NODE_NAME.
PACKAGE defaults to PROJECT_NAME. NODE_NAMESPACE defaults to /.
TIMEOUT defaults to 15 seconds.
]=]

set(_nodl_conformance_cmake_dir "${CMAKE_CURRENT_LIST_DIR}")

function(_nodl_conformance_python_string output value)
  string(REPLACE "\\" "\\\\" _escaped "${value}")
  string(REPLACE "'" "\\'" _escaped "${_escaped}")
  string(REPLACE "\n" "\\n" _escaped "${_escaped}")
  string(REPLACE "\r" "\\r" _escaped "${_escaped}")
  set(${output} "'${_escaped}'" PARENT_SCOPE)
endfunction()

function(nodl_add_conformance_test test_name)
  cmake_parse_arguments(
    _ARGS
    ""
    "PACKAGE;EXECUTABLE;NODL_FILE;NODE_NAME;NODE_NAMESPACE;TIMEOUT"
    ""
    ${ARGN}
  )

  if(NOT test_name)
    message(FATAL_ERROR "nodl_add_conformance_test: test name is required")
  endif()
  foreach(_required EXECUTABLE NODL_FILE NODE_NAME)
    if(NOT _ARGS_${_required})
      message(FATAL_ERROR "nodl_add_conformance_test: ${_required} is required")
    endif()
  endforeach()

  if(NOT _ARGS_PACKAGE)
    set(_ARGS_PACKAGE "${PROJECT_NAME}")
  endif()
  if(NOT _ARGS_NODE_NAMESPACE)
    set(_ARGS_NODE_NAMESPACE "/")
  endif()
  if(NOT DEFINED _ARGS_TIMEOUT)
    set(_ARGS_TIMEOUT 15)
  endif()
  if(NOT _ARGS_TIMEOUT MATCHES "^[1-9][0-9]*$")
    message(FATAL_ERROR "nodl_add_conformance_test: TIMEOUT must be a positive integer")
  endif()

  get_filename_component(
    _nodl_file
    "${_ARGS_NODL_FILE}"
    ABSOLUTE
    BASE_DIR "${CMAKE_CURRENT_SOURCE_DIR}"
  )
  if(NOT EXISTS "${_nodl_file}")
    message(FATAL_ERROR "nodl_add_conformance_test: NODL_FILE does not exist: ${_nodl_file}")
  endif()

  if(NOT COMMAND add_launch_test)
    find_package(launch_testing_ament_cmake REQUIRED)
  endif()

  _nodl_conformance_python_string(_package_python "${_ARGS_PACKAGE}")
  _nodl_conformance_python_string(_executable_python "${_ARGS_EXECUTABLE}")
  _nodl_conformance_python_string(_nodl_file_python "${_nodl_file}")
  _nodl_conformance_python_string(_node_name_python "${_ARGS_NODE_NAME}")
  _nodl_conformance_python_string(_node_namespace_python "${_ARGS_NODE_NAMESPACE}")

  set(_generated_dir "${CMAKE_CURRENT_BINARY_DIR}/nodl_conformance")
  file(MAKE_DIRECTORY "${_generated_dir}")
  set(_generated_test "${_generated_dir}/${test_name}.py")
  configure_file(
    "${_nodl_conformance_cmake_dir}/nodl_conformance_test.py.in"
    "${_generated_test}"
    @ONLY
  )

  math(EXPR _ctest_timeout "${_ARGS_TIMEOUT} + 10")
  add_launch_test(
    "${_generated_test}"
    TARGET "${test_name}"
    TIMEOUT "${_ctest_timeout}"
  )
endfunction()
