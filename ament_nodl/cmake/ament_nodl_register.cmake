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
# The document is also installed as YAML under ``share/<package>/nodl/`` for direct filesystem access.
#
# ``local://`` includes are rewritten to ``nodl://<package>/<name>`` references on install.
# Every ``local://`` target must itself be registered in the same package, an unregistered sibling would not be reachable downstream.
# The rewrite is deferred until all registrations in the directory are known, so registration order does not matter.
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

  # Record this document, mapping the source path to package+name to drive rewrite and install.
  # Rewrite and install are deferred so all docs registered in this directory are available at rewrite time.
  set_property(GLOBAL APPEND PROPERTY _AMENT_NODL_MAP_PATHS "${_abs_file}")
  set_property(GLOBAL APPEND PROPERTY _AMENT_NODL_MAP_PKGS "${_ARGS_PACKAGE}")
  set_property(GLOBAL APPEND PROPERTY _AMENT_NODL_MAP_NAMES "${resource_name}")

  get_property(_scheduled DIRECTORY PROPERTY _AMENT_NODL_FINALIZE_SCHEDULED)
  if(NOT _scheduled)
    set_property(DIRECTORY PROPERTY _AMENT_NODL_FINALIZE_SCHEDULED TRUE)
    cmake_language(DEFER CALL _ament_nodl_finalize)
  endif()
endfunction()

# Run once at the end of the directory scope, after all ament_nodl_register calls have been made.
function(_ament_nodl_finalize)
  set(_NODL_RESOURCE_TYPE "nodl")
  set(_work_dir "${CMAKE_CURRENT_BINARY_DIR}/ament_nodl")

  get_property(_map_paths GLOBAL PROPERTY _AMENT_NODL_MAP_PATHS)
  get_property(_map_pkgs GLOBAL PROPERTY _AMENT_NODL_MAP_PKGS)
  get_property(_map_names GLOBAL PROPERTY _AMENT_NODL_MAP_NAMES)

  # One rewrite rule per registered document: its absolute source path -> its nodl:// reference.
  # Every document's rewrite is given the full set, since any of them may include any other.
  set(_ref_args "")
  list(LENGTH _map_paths _count)
  math(EXPR _last "${_count} - 1")
  foreach(_i RANGE ${_last})
    list(GET _map_paths ${_i} _p)
    list(GET _map_pkgs ${_i} _pkg)
    list(GET _map_names ${_i} _nm)
    list(APPEND _ref_args -r "local://${_p}:=nodl://${_pkg}/${_nm}")
  endforeach()

  # Rewrite and install each registered document.
  foreach(_i RANGE ${_last})
    list(GET _map_paths ${_i} _abs_file)
    list(GET _map_pkgs ${_i} _pkg)
    list(GET _map_names ${_i} _name)
    set(_key "${_pkg}__${_name}")
    set(_out "${_work_dir}/rewritten/${_key}")
    # The share copy keeps the source stem but is uniformly YAML (its content is now YAML).
    get_filename_component(_stem "${_abs_file}" NAME_WLE)

    # Rewrite refs.
    # Depends on the source and on the directory's CMakeLists so a change to the registered set retriggers the rewrite.
    add_custom_command(
      OUTPUT "${_out}"
      DEPENDS "${_abs_file}" "${CMAKE_CURRENT_SOURCE_DIR}/CMakeLists.txt"
      COMMAND "${Python3_EXECUTABLE}" -m ros2nodl rewrite ${_ref_args}
        --output "${_out}" "${_abs_file}"
      COMMENT "Rewriting NoDL ${_key}"
      VERBATIM
    )
    add_custom_target(_ament_nodl_rewrite_${_key} ALL DEPENDS "${_out}")

    # Install the rewritten (YAML) document to the ament index (keyed) and to the package share dir.
    install(
      FILES "${_out}"
      DESTINATION "share/ament_index/resource_index/${_NODL_RESOURCE_TYPE}"
      RENAME "${_key}")
    install(
      FILES "${_out}"
      DESTINATION "share/${_pkg}/nodl"
      RENAME "${_stem}.yaml")
  endforeach()
endfunction()
