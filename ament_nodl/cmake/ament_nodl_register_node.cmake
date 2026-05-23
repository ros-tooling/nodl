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
  cmake_parse_arguments(_ANN "" "FILE;PACKAGE" "" ${ARGN})

  if(NOT _ANN_FILE)
    message(FATAL_ERROR "ament_nodl_register_node: FILE is required")
  endif()
  if(NOT _ANN_PACKAGE)
    set(_ANN_PACKAGE "${PROJECT_NAME}")
  endif()

  get_filename_component(_abs_file "${_ANN_FILE}" ABSOLUTE
    BASE_DIR "${CMAKE_CURRENT_SOURCE_DIR}")

  if(NOT EXISTS "${_abs_file}")
    message(WARNING
      "ament_nodl_register_node: file not found at configure time: ${_abs_file}")
  endif()

  # Both installs reference the source file directly so they pick up its
  # current bytes at install time, not a snapshot from configure time.
  install(
    FILES "${_abs_file}"
    DESTINATION "share/ament_index/resource_index/nodl_nodes"
    RENAME "${_ANN_PACKAGE}__${executable_name}")

  install(
    FILES "${_abs_file}"
    DESTINATION "share/${_ANN_PACKAGE}/nodl")
endfunction()
