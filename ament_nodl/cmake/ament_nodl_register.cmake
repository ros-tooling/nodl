# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
#
# Register a NoDL file in the ament resource index, validating it at build time.
#
# This is the common implementation behind ament_nodl_register_node and
# ament_nodl_register_interface; prefer those wrappers. The TYPE selects how the
# file is validated and where it is published:
#
#   TYPE node       -> validated as a node definition (base/main/mixins);
#                      resource type ``nodl_nodes``;      installed under share/<pkg>/nodl/
#   TYPE interface  -> validated as a (partial) interface definition;
#                      resource type ``nodl_interfaces``; installed under share/<pkg>/nodl/interfaces/
#
# In both cases the resource key is ``<package>__<name>`` and the source file is
# also installed to the package share tree for direct filesystem access.
# Validation runs at build time (only when the file changes) so authoring errors
# surface in the owning package's build, not downstream when consuming.
#
# :param name: resource name, combined with PACKAGE to form the ``<package>__<name>`` key.
# :type name: string
# :param TYPE: ``node`` or ``interface``.
# :type TYPE: string
# :param FILE: path to the NoDL file. May be absolute or relative to ``CMAKE_CURRENT_SOURCE_DIR``.
# :type FILE: string
# :param PACKAGE: package name to use in the resource key. Defaults to ``${PROJECT_NAME}``.
# :type PACKAGE: string
#
# @public
#
function(ament_nodl_register name)
  cmake_parse_arguments(_ARGS "" "TYPE;FILE;PACKAGE" "" ${ARGN})

  if(NOT _ARGS_FILE)
    message(FATAL_ERROR "ament_nodl_register: FILE is required")
  endif()
  if(NOT _ARGS_PACKAGE)
    set(_ARGS_PACKAGE "${PROJECT_NAME}")
  endif()

  # TYPE selects the resource type, validation mode, and install subdirectory.
  if(_ARGS_TYPE STREQUAL "node")
    set(_resource_type "nodl_nodes")
    set(_validate_flag "--node")
    set(_share_subdir "nodl")
  elseif(_ARGS_TYPE STREQUAL "interface")
    set(_resource_type "nodl_interfaces")
    set(_validate_flag "")  # interface definitions use the default validator
    set(_share_subdir "nodl/interfaces")
  else()
    message(FATAL_ERROR
      "ament_nodl_register: TYPE must be 'node' or 'interface', got '${_ARGS_TYPE}'")
  endif()

  get_filename_component(_abs_file "${_ARGS_FILE}" ABSOLUTE
    BASE_DIR "${CMAKE_CURRENT_SOURCE_DIR}")

  if(NOT EXISTS "${_abs_file}")
    message(WARNING
      "ament_nodl_register: file not found at configure time: ${_abs_file}")
  endif()

  # Validate the file at build time. This only runs when ${_abs_file} changes.
  set(_key "${_ARGS_PACKAGE}__${name}")
  set(_stamp_dir "${CMAKE_CURRENT_BINARY_DIR}/ament_nodl/${_resource_type}")
  set(_stamp "${_stamp_dir}/${_key}.valid.stamp")
  file(MAKE_DIRECTORY "${_stamp_dir}")
  add_custom_command(
    OUTPUT "${_stamp}"
    DEPENDS "${_abs_file}"
    COMMAND "${Python3_EXECUTABLE}" -m nodl_schema ${_validate_flag} "${_abs_file}"
    COMMAND "${CMAKE_COMMAND}" -E touch "${_stamp}"
    COMMENT "Validating NoDL ${_ARGS_TYPE} ${_ARGS_PACKAGE}/${name}"
    VERBATIM
  )
  add_custom_target(_ament_nodl_validate_${_ARGS_TYPE}_${_key} ALL
    DEPENDS "${_stamp}"
  )

  # Install to the ament index.
  install(
    FILES "${_abs_file}"
    DESTINATION "share/ament_index/resource_index/${_resource_type}"
    RENAME "${_key}")

  # Install to the package's share directory for direct filesystem access.
  install(
    FILES "${_abs_file}"
    DESTINATION "share/${_ARGS_PACKAGE}/${_share_subdir}")
endfunction()


# Register a NoDL node definition for an executable (TYPE node).
#
# The file is a NoDL node definition (``node.schema.yaml``): a ``base`` +
# ``mixins`` + ``main`` composition describing the executable's whole interface.
# Published under the ``nodl_nodes`` resource type with key
# ``<package>__<executable>``; tools locate it via
# ``get_resource('nodl_nodes', '<pkg>__<exe>')``.
#
# Example::
#
#   ament_nodl_register_node(my_node FILE nodl/my_node.nodl.yaml)
#
# @public
#
function(ament_nodl_register_node executable_name)
  ament_nodl_register("${executable_name}" TYPE node ${ARGN})
endfunction()


# Register a reusable NoDL interface definition (TYPE interface).
#
# Published under the ``nodl_interfaces`` resource type with key
# ``<package>__<name>``; node definitions pull it in as a mixin via
# ``nodl://<package>/<name>``.
#
# Example::
#
#   ament_nodl_register_interface(tf_listener FILE nodl/tf_listener.nodl.yaml)
#
# @public
#
function(ament_nodl_register_interface interface_name)
  ament_nodl_register("${interface_name}" TYPE interface ${ARGN})
endfunction()
