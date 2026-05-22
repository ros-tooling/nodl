# ament_nodl_register_fragment(name
#   FILE <path>
#   [PACKAGE <pkg>]    # defaults to ${PROJECT_NAME}
# )
#
# Registers a NoDL fragment in the ament resource index under resource type
# 'nodl_fragments', keyed as '<package>__<name>'.
#
# The fragment YAML content is stored as the resource value so that consumers
# can retrieve it via:
#   ament_index_python.packages.get_resource('nodl_fragments', '<pkg>__<name>')
#
# In NoDL files, reference this fragment as:
#   ref: nodl://<package>/<name>
#
# Example:
#   ament_nodl_register_fragment(tf_listener
#     FILE nodl/tf_listener.nodl.yaml
#   )
#
function(ament_nodl_register_fragment fragment_name)
  cmake_parse_arguments(_ANF "" "FILE;PACKAGE" "" ${ARGN})

  if(NOT _ANF_FILE)
    message(FATAL_ERROR "ament_nodl_register_fragment: FILE is required")
  endif()
  if(NOT _ANF_PACKAGE)
    set(_ANF_PACKAGE "${PROJECT_NAME}")
  endif()

  get_filename_component(_abs_file "${_ANF_FILE}" ABSOLUTE
    BASE_DIR "${CMAKE_CURRENT_SOURCE_DIR}")

  if(NOT EXISTS "${_abs_file}")
    message(WARNING
      "ament_nodl_register_fragment: file not found at configure time: ${_abs_file}")
  endif()

  # Read the NoDL file content at configure time and embed it in the marker.
  file(READ "${_abs_file}" _nodl_content)

  set(_resource_key "${_ANF_PACKAGE}__${fragment_name}")
  set(_marker_dir
    "${CMAKE_CURRENT_BINARY_DIR}/ament_nodl/nodl_fragments")
  file(MAKE_DIRECTORY "${_marker_dir}")
  file(WRITE "${_marker_dir}/${_resource_key}" "${_nodl_content}")

  install(
    FILES "${_marker_dir}/${_resource_key}"
    DESTINATION "share/ament_index/resource_index/nodl_fragments")

  # Also install the source file for human reference.
  install(
    FILES "${_abs_file}"
    DESTINATION "share/${_ANF_PACKAGE}/nodl/fragments")
endfunction()
