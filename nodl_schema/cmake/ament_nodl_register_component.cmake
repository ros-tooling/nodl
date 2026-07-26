# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
#
# Register a NoDL spec for a composable node component.
#
# Installs the NoDL file (via ``ament_nodl_install``) and registers a mapping
# from the fully-qualified component class name to the installed NoDL file
# under the ``nodl_components`` ament index resource type.
#
# Resource content (one line per component, appended)::
#
#   my_pkg::FooNode:nodl/foo.nodl.yaml
#
# Example::
#
#   ament_nodl_register_component(my_pkg::FooNode
#     FILE nodl/foo.nodl.yaml
#   )
#
# :param component_class: fully-qualified class name of the composable node.
# :type component_class: string
# :param FILE: path to the NoDL file describing the component's interface.
#   May be absolute or relative to ``CMAKE_CURRENT_SOURCE_DIR``.
# :type FILE: string
#
# @public
#
function(ament_nodl_register_component component_class)
  cmake_parse_arguments(_ARGS "" "FILE" "" ${ARGN})

  if(NOT _ARGS_FILE)
    message(FATAL_ERROR "ament_nodl_register_component: FILE is required")
  endif()

  # Install and validate the NoDL file.
  ament_nodl_install(FILES "${_ARGS_FILE}")

  # Resolve the filename for the resource entry.
  get_filename_component(_filename "${_ARGS_FILE}" NAME)

  # Register the component → NoDL mapping.
  ament_index_register_resource(nodl_components
    CONTENT "${component_class}:nodl/${_filename}\n")
endfunction()
