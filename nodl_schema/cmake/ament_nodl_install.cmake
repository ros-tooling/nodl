# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
#
# Validate and install NoDL interface files.
#
# Validates each file at build time using ``nodl_schema``, installs to
# ``share/<package>/nodl/``, and registers the filenames under the
# ``nodl_interfaces`` ament index resource type.
#
# Idempotent — safe to call multiple times for the same file (e.g. when a
# higher-level macro such as ``ament_nodl_register_executable`` also calls it
# internally).  Duplicate registrations for the same absolute path are skipped.
#
# The actual ``ament_index_register_resource`` call is deferred to
# ``ament_package()`` time via an extension hook, so multiple calls to this
# function accumulate filenames into a single resource entry rather than
# conflicting.
#
# Example::
#
#   ament_nodl_install(
#     FILES
#       nodl/foo.nodl.yaml
#       nodl/bar.nodl.yaml
#   )
#
# :param FILES: one or more NoDL files to install.
#   Paths may be absolute or relative to ``CMAKE_CURRENT_SOURCE_DIR``.
# :type FILES: list of strings
#
# @public
#
function(ament_nodl_install)
  cmake_parse_arguments(_ARGS "" "" "FILES" ${ARGN})

  if(NOT _ARGS_FILES)
    message(FATAL_ERROR "ament_nodl_install: FILES is required")
  endif()

  foreach(_file ${_ARGS_FILES})
    get_filename_component(_abs_file "${_file}" ABSOLUTE
      BASE_DIR "${CMAKE_CURRENT_SOURCE_DIR}")

    # Idempotency: skip if this file has already been registered.
    get_property(_installed_files GLOBAL PROPERTY _AMENT_NODL_INSTALLED_FILES)
    if("${_abs_file}" IN_LIST _installed_files)
      continue()
    endif()
    set_property(GLOBAL APPEND PROPERTY _AMENT_NODL_INSTALLED_FILES "${_abs_file}")

    if(NOT EXISTS "${_abs_file}")
      message(WARNING
        "ament_nodl_install: file not found at configure time: ${_abs_file}")
    endif()

    get_filename_component(_filename "${_abs_file}" NAME)

    # Validate at build time.
    set(_stamp_dir "${CMAKE_CURRENT_BINARY_DIR}/ament_nodl/nodl_interfaces")
    set(_stamp "${_stamp_dir}/${_filename}.valid.stamp")
    file(MAKE_DIRECTORY "${_stamp_dir}")
    add_custom_command(
      OUTPUT "${_stamp}"
      DEPENDS "${_abs_file}"
      COMMAND "${Python3_EXECUTABLE}" -m nodl_schema "${_abs_file}"
      COMMAND "${CMAKE_COMMAND}" -E touch "${_stamp}"
      COMMENT "Validating NoDL file ${_filename}"
      VERBATIM
    )
    add_custom_target(_ament_nodl_validate_${_filename} ALL
      DEPENDS "${_stamp}"
    )

    # Install to share/<pkg>/nodl/
    install(
      FILES "${_abs_file}"
      DESTINATION "share/${PROJECT_NAME}/nodl")

    # Accumulate filenames for bulk registration at ament_package() time.
    set_property(GLOBAL APPEND PROPERTY _AMENT_NODL_INTERFACE_FILENAMES "${_filename}")
  endforeach()
endfunction()
