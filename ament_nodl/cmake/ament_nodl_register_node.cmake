# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
#
# Register a NoDL node composition for an executable in the ament resource index.
#
# The file is a NoDL node (``node.schema.yaml``): a ``base`` + ``mixins`` + ``main``
# composition describing the executable's whole interface.
#
# Publishes the contents of the file under the ``nodl_nodes`` resource type.
# The resource key is ``<package>__<executable>``.
# Tools like ``nodl_test`` and ``nodl_docgen`` use this to locate the spec by package and executable name.
#
# Consumers retrieve the content via::
#
#   ament_index_python.packages.get_resource('nodl_nodes', '<pkg>__<exe>')
#
# The source file is also installed under ``share/<package>/nodl/`` for direct filesystem access.
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

  # Validate the file at build time so authoring errors surface when registering, not downstream when consuming.
  # This only runs when ${_abs_file} changes.
  set(_stamp_dir "${CMAKE_CURRENT_BINARY_DIR}/ament_nodl/nodl_nodes")
  set(_stamp "${_stamp_dir}/${_ARGS_PACKAGE}__${executable_name}.valid.stamp")
  file(MAKE_DIRECTORY "${_stamp_dir}")
  add_custom_command(
    OUTPUT "${_stamp}"
    DEPENDS "${_abs_file}"
    COMMAND "${Python3_EXECUTABLE}" -m nodl_schema --node "${_abs_file}"
    COMMAND "${CMAKE_COMMAND}" -E touch "${_stamp}"
    COMMENT "Validating NoDL node ${_ARGS_PACKAGE}/${executable_name}"
    VERBATIM
  )
  add_custom_target(_ament_nodl_validate_node_${_ARGS_PACKAGE}__${executable_name} ALL
    DEPENDS "${_stamp}"
  )

  # Install to ament index
  install(
    FILES "${_abs_file}"
    DESTINATION "share/ament_index/resource_index/nodl_nodes"
    RENAME "${_ARGS_PACKAGE}__${executable_name}")

  # Install to package's share directory
  install(
    FILES "${_abs_file}"
    DESTINATION "share/${_ARGS_PACKAGE}/nodl")
endfunction()
