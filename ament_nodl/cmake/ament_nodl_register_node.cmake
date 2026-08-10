# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
#
# Register a NoDL document for an executable in the ament resource index.
#
# Publishes the contents of a NoDL file under the ``nodl_nodes`` resource type.
# The resource key is ``<package>__<executable>``.
# Tools like ``nodl_test`` and ``nodl_docgen`` use this to locate the spec by package and executable name.
#
# Consumers retrieve the content via::
#
#   ament_index_python.packages.get_resource('nodl_nodes', '<pkg>__<exe>')
#
# The source file is also installed under ``share/<package>/nodl/`` for direct filesystem access.
#
# If the document uses ``local://`` includes, what installs is a rewritten copy in which each has
# become ``nodl://<package>/<name>``.
# A relative reference means nothing to a consumer reading the document out of the index, so it is
# replaced by a name that does.
# The referenced document must already be registered by an earlier call, which supplies that name.
#
# Example::
#
#   ament_nodl_register_node(my_node
#     FILE nodl/my_node.nodl.yaml
#   )
#
# :param executable_name: name of the executable this NoDL document describes.
#   Combined with PACKAGE to form the resource key.
# :type executable_name: string
# :param FILE: path to the NoDL file describing the executable's interface.
#   May be absolute or relative to ``CMAKE_CURRENT_SOURCE_DIR``.
# :type FILE: string
# :param PACKAGE: package name to use in the resource key.
#   Defaults to ``${PROJECT_NAME}``.
# :type PACKAGE: string
#
# @public
#
function(ament_nodl_register_node executable_name)
  cmake_parse_arguments(_ARGS "" "FILE;PACKAGE" "" ${ARGN})

  if(NOT _ARGS_FILE)
    message(FATAL_ERROR "ament_nodl_register_node: FILE is required")
  endif()
  if(NOT _ARGS_PACKAGE)
    set(_ARGS_PACKAGE "${PROJECT_NAME}")
  endif()

  get_filename_component(_abs_file "${_ARGS_FILE}" ABSOLUTE
    BASE_DIR "${CMAKE_CURRENT_SOURCE_DIR}")

  if(NOT EXISTS "${_abs_file}")
    message(WARNING
      "ament_nodl_register_node: file not found at configure time: ${_abs_file}")
  endif()

  _ament_nodl_record_registration("${_abs_file}" "${_ARGS_PACKAGE}" "${executable_name}")
  _ament_nodl_local_references("${_abs_file}" _local_refs)
  _ament_nodl_name_map(_map_args)

  # Every local reference must already be registered, so the rewrite cannot fail on a name that
  # does not exist. Checking at configure time puts the error where the fix is: the order of calls
  # in this CMakeLists.
  get_property(_registered GLOBAL PROPERTY _AMENT_NODL_REGISTERED_PATHS)
  foreach(_ref IN LISTS _local_refs)
    if(NOT "${_ref}" IN_LIST _registered)
      message(FATAL_ERROR
        "ament_nodl_register_node(${executable_name}): ${_abs_file} references ${_ref}, "
        "which is not registered.\n"
        "Add an ament_nodl_register_node() call for it above this one.")
    endif()
  endforeach()

  # Validate the file at build time so authoring errors surface when registering, not downstream
  # when consuming. Rewriting reads only ${_abs_file}, but validation follows local references into
  # the source tree, so this reruns when any of those change too.
  get_filename_component(_basename "${_abs_file}" NAME)
  set(_gen_dir "${CMAKE_CURRENT_BINARY_DIR}/ament_nodl/${_ARGS_PACKAGE}__${executable_name}")
  set(_gen_file "${_gen_dir}/${_basename}")
  add_custom_command(
    OUTPUT "${_gen_file}"
    DEPENDS "${_abs_file}" ${_local_refs}
    COMMAND "${Python3_EXECUTABLE}" -m nodl_schema "${_abs_file}"
    COMMAND "${Python3_EXECUTABLE}" -m nodl_schema "${_abs_file}"
      --rewrite-to "${_gen_file}" --package "${_ARGS_PACKAGE}" ${_map_args}
    COMMENT "Validating NoDL node ${_ARGS_PACKAGE}/${executable_name}"
    VERBATIM
  )
  add_custom_target(_ament_nodl_validate_node_${_ARGS_PACKAGE}__${executable_name} ALL
    DEPENDS "${_gen_file}"
  )

  # Install to ament index
  install(
    FILES "${_gen_file}"
    DESTINATION "share/ament_index/resource_index/nodl_nodes"
    RENAME "${_ARGS_PACKAGE}__${executable_name}")

  # Install to package's share directory
  install(
    FILES "${_gen_file}"
    DESTINATION "share/${_ARGS_PACKAGE}/nodl")
endfunction()

#
# Record a registration so later calls can rewrite local references pointing at it.
#
# Two parallel global lists hold the record: an absolute path, and the ``<package>/<name>`` it was
# registered as. A name may map to only one file, since a second registration would quietly take
# over a name that an already-rewritten reference points at.
#
function(_ament_nodl_record_registration abs_file package name)
  get_property(_paths GLOBAL PROPERTY _AMENT_NODL_REGISTERED_PATHS)
  get_property(_targets GLOBAL PROPERTY _AMENT_NODL_REGISTERED_TARGETS)
  set(_target "${package}/${name}")

  list(FIND _targets "${_target}" _index)
  if(NOT _index EQUAL -1)
    list(GET _paths ${_index} _existing)
    if(NOT "${_existing}" STREQUAL "${abs_file}")
      message(FATAL_ERROR
        "ament_nodl_register_node: ${_target} is already registered from a different file.\n"
        "  first:  ${_existing}\n"
        "  second: ${abs_file}\n"
        "A name may refer to only one document, since references are rewritten to it by name.")
    endif()
    message(FATAL_ERROR
      "ament_nodl_register_node: ${_target} is already registered from ${abs_file}.\n"
      "Remove the duplicate call.")
  endif()

  set_property(GLOBAL APPEND PROPERTY _AMENT_NODL_REGISTERED_PATHS "${abs_file}")
  set_property(GLOBAL APPEND PROPERTY _AMENT_NODL_REGISTERED_TARGETS "${_target}")
endfunction()

#
# Return the documents reachable from a file through local references, transitively.
#
# Also marks them as configure dependencies, so adding or removing a reference in any of them
# reruns configure and refreshes this list.
#
function(_ament_nodl_local_references abs_file out_var)
  # A document generated by another custom command does not exist yet, and registering one is
  # supported (the missing-file case is a warning above, not an error). There is nothing to read.
  if(NOT EXISTS "${abs_file}")
    set(${out_var} "" PARENT_SCOPE)
    return()
  endif()

  execute_process(
    COMMAND "${Python3_EXECUTABLE}" -m nodl_schema "${abs_file}" --list-references
    OUTPUT_VARIABLE _output
    ERROR_VARIABLE _error
    RESULT_VARIABLE _result
    OUTPUT_STRIP_TRAILING_WHITESPACE
  )
  # Reading includes is best-effort. A document that cannot be parsed at configure time still gets
  # validated at build time, which is where that error belongs and reads better.
  if(NOT _result EQUAL 0)
    set(${out_var} "" PARENT_SCOPE)
    return()
  endif()

  string(REPLACE "\n" ";" _refs "${_output}")
  list(REMOVE_ITEM _refs "")
  if(_refs)
    set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS ${_refs})
  endif()
  set(${out_var} "${_refs}" PARENT_SCOPE)
endfunction()

#
# Build the ``--map <path>=<package>/<name>`` arguments describing every registration so far.
#
function(_ament_nodl_name_map out_var)
  get_property(_paths GLOBAL PROPERTY _AMENT_NODL_REGISTERED_PATHS)
  get_property(_targets GLOBAL PROPERTY _AMENT_NODL_REGISTERED_TARGETS)

  set(_args "")
  list(LENGTH _paths _count)
  if(_count GREATER 0)
    math(EXPR _last "${_count} - 1")
    foreach(_i RANGE ${_last})
      list(GET _paths ${_i} _path)
      list(GET _targets ${_i} _target)
      list(APPEND _args "--map" "${_path}=${_target}")
    endforeach()
  endif()
  set(${out_var} "${_args}" PARENT_SCOPE)
endfunction()
