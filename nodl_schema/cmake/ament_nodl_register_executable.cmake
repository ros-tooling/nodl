# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
#
# Register a NoDL spec for a standalone node executable.
#
# Installs the NoDL file (via ``ament_nodl_install``) and registers a mapping
# from the executable name to the installed NoDL file under the
# ``nodl_executables`` ament index resource type.
#
# Resource content (one line per executable, appended)::
#
#   foo_node:nodl/foo.nodl.yaml
#
# Example::
#
#   ament_nodl_register_executable(foo_node
#     FILE nodl/foo.nodl.yaml
#   )
#
# :param executable_name: name of the executable this NoDL document describes.
# :type executable_name: string
# :param FILE: path to the NoDL file describing the executable's interface.
#   May be absolute or relative to ``CMAKE_CURRENT_SOURCE_DIR``.
# :type FILE: string
#
# @public
#
function(ament_nodl_register_executable executable_name)
  cmake_parse_arguments(_ARGS "" "FILE" "" ${ARGN})

  if(NOT _ARGS_FILE)
    message(FATAL_ERROR "ament_nodl_register_executable: FILE is required")
  endif()

  # Install and validate the NoDL file.
  ament_nodl_install(FILES "${_ARGS_FILE}")

  # Resolve the filename for the resource entry.
  get_filename_component(_filename "${_ARGS_FILE}" NAME)

  # Register the executable → NoDL mapping.
  ament_index_register_resource(nodl_executables
    CONTENT "${executable_name}:nodl/${_filename}\n")
endfunction()
