# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
#
# Register a NoDL document in the ament resource index.
#
# Publishes the contents of a NoDL file under the ``nodl`` resource type.
# The resource key is ``<package>__<resource_name>``.
#
# Consumers may retrieve the content via::
#
#   ament_index_python.packages.get_resource('nodl', '<pkg>__<name>')
#
# The source file is also installed under ``share/<package>/nodl/`` for direct filesystem access.
#
# Example::
#
#   ament_nodl_register(my_node
#     FILE nodl/my_node.nodl.yaml
#   )
#
# :param resource_name: target name for this NoDL document.
# :type resource_name: string
# :param FILE: Required path to the NoDL file describing the executable's interface.
#   May be absolute or relative to ``CMAKE_CURRENT_SOURCE_DIR``.
# :type FILE: string
# :param PACKAGE: package name to use in the resource key.
#   Defaults to ``${PROJECT_NAME}``.
# :type PACKAGE: string
#
# @public
#
function(ament_nodl_register resource_name)
  cmake_parse_arguments(_ARGS "" "FILE;PACKAGE" "" ${ARGN})
  set(_NODL_RESOURCE_TYPE "nodl")

  if(NOT _ARGS_FILE)
    message(FATAL_ERROR "${CMAKE_CURRENT_FUNCTION}: FILE is required")
  endif()
  if(NOT _ARGS_PACKAGE)
    set(_ARGS_PACKAGE "${PROJECT_NAME}")
  endif()

  get_filename_component(_abs_file "${_ARGS_FILE}" ABSOLUTE
    BASE_DIR "${CMAKE_CURRENT_SOURCE_DIR}")

  if(NOT EXISTS "${_abs_file}")
    message(WARNING
      "${CMAKE_CURRENT_FUNCTION}: file not found at configure time: ${_abs_file}")
  endif()

  # Validate the file at build time so authoring errors surface when registering, not downstream when consuming.
  # This only runs when ${_abs_file} changes.
  set(_stamp_dir "${CMAKE_CURRENT_BINARY_DIR}/ament_nodl/${_NODL_RESOURCE_TYPE}")
  set(_stamp "${_stamp_dir}/${_ARGS_PACKAGE}__${resource_name}.valid.stamp")
  file(MAKE_DIRECTORY "${_stamp_dir}")
  add_custom_command(
    OUTPUT "${_stamp}"
    DEPENDS "${_abs_file}"
    COMMAND "${Python3_EXECUTABLE}" -m ros2nodl validate "${_abs_file}"
    COMMAND "${CMAKE_COMMAND}" -E touch "${_stamp}"
    COMMENT "Validating NoDL ${_ARGS_PACKAGE}/${resource_name}"
    VERBATIM
  )
  add_custom_target(_ament_nodl_validate_node_${_ARGS_PACKAGE}__${resource_name} ALL
    DEPENDS "${_stamp}"
  )

  # Install to ament index
  install(
    FILES "${_abs_file}"
    DESTINATION "share/ament_index/resource_index/${_NODL_RESOURCE_TYPE}"
    RENAME "${_ARGS_PACKAGE}__${resource_name}")

  # Install to package's share directory
  install(
    FILES "${_abs_file}"
    DESTINATION "share/${_ARGS_PACKAGE}/nodl")
endfunction()
