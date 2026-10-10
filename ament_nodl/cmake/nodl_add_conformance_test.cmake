# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0

set(_nodl_conformance_cmake_dir "${CMAKE_CURRENT_LIST_DIR}")

function(_nodl_conformance_python_string output value)
  string(REPLACE "\\" "\\\\" _escaped "${value}")
  string(REPLACE "'" "\\'" _escaped "${_escaped}")
  string(REPLACE "\n" "\\n" _escaped "${_escaped}")
  string(REPLACE "\r" "\\r" _escaped "${_escaped}")
  set(${output} "'${_escaped}'" PARENT_SCOPE)
endfunction()

#
# Register a launch test that compares one executable with one NoDL document.
#
# Finds ``launch_testing_ament_cmake`` on every call, because the variables ``add_launch_test`` reads are set in the calling scope.
#
# :param test_name: name of the test target to create.
# :type test_name: string
# :param EXECUTABLE: Required executable to launch and compare against the document.
# :type EXECUTABLE: string
# :param NODL_FILE: Required path to the NoDL file, absolute or relative to ``CMAKE_CURRENT_SOURCE_DIR``.
# :type NODL_FILE: string
# :param NODE_NAME: name of the node the executable runs.
#   Defaults to ``test_name``, which must then be a valid node name.
# :type NODE_NAME: string
# :param PACKAGE: package that provides the executable.
#   Defaults to ``${PROJECT_NAME}``.
# :type PACKAGE: string
# :param NODE_NAMESPACE: namespace of the node.
#   Defaults to ``/``.
# :type NODE_NAMESPACE: string
# :param TIMEOUT: positive integer number of seconds to wait for the node.
#   Defaults to 15.
# :type TIMEOUT: integer
# :param PARAMETERS: ``name:=value`` items passed to the node as ``-p`` arguments, for nodes with required parameters that have no default.
#   Items use the syntax of ``ros2 run -p``, so name and value must be non-empty.
#   Items are applied after ``PARAMETERS_FILE`` and override the same parameter set there.
# :type PARAMETERS: list of strings
# :param PARAMETERS_FILE: YAML parameter files passed to the node as ``--params-file`` arguments.
#   Each is absolute or relative to ``CMAKE_CURRENT_SOURCE_DIR``.
# :type PARAMETERS_FILE: list of strings
# :param IGNORE: ignore rules, each ``KIND:NAME[:TYPE]``, such as ``publisher:/topic_statistics``.
#   Observed entities that a rule selects and the document does not declare are left out of the comparison.
#   See ``ros2nodl`` ``conform`` for the rule syntax.
# :type IGNORE: list of strings
#
# @public
#
function(nodl_add_conformance_test test_name)
  cmake_parse_arguments(
    _ARGS
    ""
    "PACKAGE;EXECUTABLE;NODL_FILE;NODE_NAME;NODE_NAMESPACE;TIMEOUT"
    "PARAMETERS;PARAMETERS_FILE;IGNORE"
    ${ARGN}
  )

  if(NOT test_name)
    message(FATAL_ERROR "nodl_add_conformance_test: test name is required")
  endif()
  foreach(_required EXECUTABLE NODL_FILE)
    if(NOT _ARGS_${_required})
      message(FATAL_ERROR "nodl_add_conformance_test: ${_required} is required")
    endif()
  endforeach()

  if(NOT _ARGS_NODE_NAME)
    if(NOT test_name MATCHES "^[A-Za-z_][A-Za-z0-9_]*$")
      message(FATAL_ERROR "nodl_add_conformance_test: test name '${test_name}' is not a valid node name, pass NODE_NAME")
    endif()
    set(_ARGS_NODE_NAME "${test_name}")
  endif()
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

  set(_parameters_files_python "")
  foreach(_parameters_file IN LISTS _ARGS_PARAMETERS_FILE)
    get_filename_component(
      _parameters_file_path
      "${_parameters_file}"
      ABSOLUTE
      BASE_DIR "${CMAKE_CURRENT_SOURCE_DIR}"
    )
    if(NOT EXISTS "${_parameters_file_path}")
      message(FATAL_ERROR "nodl_add_conformance_test: PARAMETERS_FILE does not exist: ${_parameters_file_path}")
    endif()
    _nodl_conformance_python_string(_parameters_file_python "${_parameters_file_path}")
    string(APPEND _parameters_files_python "${_parameters_file_python}, ")
  endforeach()

  set(_parameters_python "")
  foreach(_parameter IN LISTS _ARGS_PARAMETERS)
    string(FIND "${_parameter}" ":=" _separator)
    string(LENGTH "${_parameter}" _parameter_length)
    math(EXPR _value_start "${_separator} + 2")
    if(_separator LESS 1 OR _value_start EQUAL _parameter_length)
      message(FATAL_ERROR "nodl_add_conformance_test: PARAMETERS item must be name:=value: '${_parameter}'")
    endif()
    _nodl_conformance_python_string(_parameter_python "${_parameter}")
    string(APPEND _parameters_python "${_parameter_python}, ")
  endforeach()

  find_package(launch_testing_ament_cmake REQUIRED)

  _nodl_conformance_python_string(_package_python "${_ARGS_PACKAGE}")
  _nodl_conformance_python_string(_executable_python "${_ARGS_EXECUTABLE}")
  _nodl_conformance_python_string(_nodl_file_python "${_nodl_file}")
  _nodl_conformance_python_string(_node_name_python "${_ARGS_NODE_NAME}")
  _nodl_conformance_python_string(_node_namespace_python "${_ARGS_NODE_NAMESPACE}")

  set(_ignore_python "")
  foreach(_rule IN LISTS _ARGS_IGNORE)
    _nodl_conformance_python_string(_rule_python "${_rule}")
    string(APPEND _ignore_python "${_rule_python}, ")
  endforeach()
  set(_ignore_python "[${_ignore_python}]")

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
