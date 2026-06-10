# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
#
# Register a reusable NoDL document in the ament resource index.
#
# Publishes the contents of a NoDL document under the ``nodl_documents`` resource type.
# The resource key is ``<package>__<name>``.
# NoDL node compositions reference the document as a mixin by ``nodl://<package>/<name>``.
#
# Consumers retrieve the content via::
#
#   ament_index_python.packages.get_resource('nodl_documents', '<pkg>__<name>')
#
# The source file is also installed under ``share/<package>/nodl/documents/`` for direct filesystem access.
#
# Example::
#
#   ament_nodl_register_document(tf_listener
#     FILE nodl/tf_listener.nodl.yaml
#   )
#
# :param document_name: name of the document.
#   Combined with PACKAGE to form the resource key and the ``nodl://<package>/<name>`` URI.
# :type document_name: string
# :param FILE: path to the NoDL file containing the document.
#   May be absolute or relative to ``CMAKE_CURRENT_SOURCE_DIR``.
# :type FILE: string
# :param PACKAGE: package name to use in the resource key.
#   Defaults to ``${PROJECT_NAME}``.
# :type PACKAGE: string
#
# @public
#
function(ament_nodl_register_document document_name)
  cmake_parse_arguments(_ARGS "" "FILE;PACKAGE" "" ${ARGN})

  if(NOT _ARGS_FILE)
    message(FATAL_ERROR "ament_nodl_register_document: FILE is required")
  endif()
  if(NOT _ARGS_PACKAGE)
    set(_ARGS_PACKAGE "${PROJECT_NAME}")
  endif()

  get_filename_component(_abs_file "${_ARGS_FILE}" ABSOLUTE
    BASE_DIR "${CMAKE_CURRENT_SOURCE_DIR}")

  if(NOT EXISTS "${_abs_file}")
    message(WARNING
      "ament_nodl_register_document: file not found at configure time: ${_abs_file}")
  endif()

  # Validate the document at build time so authoring errors surface when registering, not downstream when consuming.
  # The document schema forbids composition keys (base/main/mixins), so a node composition cannot be registered here.
  # This only runs when ${_abs_file} changes.
  set(_stamp_dir "${CMAKE_CURRENT_BINARY_DIR}/ament_nodl/nodl_documents")
  set(_stamp "${_stamp_dir}/${_ARGS_PACKAGE}__${document_name}.valid.stamp")
  file(MAKE_DIRECTORY "${_stamp_dir}")
  add_custom_command(
    OUTPUT "${_stamp}"
    DEPENDS "${_abs_file}"
    COMMAND "${Python3_EXECUTABLE}" -m nodl_schema "${_abs_file}"
    COMMAND "${CMAKE_COMMAND}" -E touch "${_stamp}"
    COMMENT "Validating NoDL document ${_ARGS_PACKAGE}/${document_name}"
    VERBATIM
  )
  add_custom_target(_ament_nodl_validate_document_${_ARGS_PACKAGE}__${document_name} ALL
    DEPENDS "${_stamp}"
  )

  # Install to ament index
  install(
    FILES "${_abs_file}"
    DESTINATION "share/ament_index/resource_index/nodl_documents"
    RENAME "${_ARGS_PACKAGE}__${document_name}")

  # Install to package's share directory
  install(
    FILES "${_abs_file}"
    DESTINATION "share/${_ARGS_PACKAGE}/nodl/documents")
endfunction()
