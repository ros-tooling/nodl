# ament_nodl_register_node(executable
#   FILE <path>
#   [PACKAGE <pkg>]    # defaults to ${PROJECT_NAME}
# )
#
# Registers a NoDL composition root (node description file) in the ament
# resource index under resource type 'nodl_nodes', keyed as
# '<package>__<executable>'.
#
# This allows tools like nodl_test and nodl_docgen to discover the NoDL
# spec for any executable by package and name without requiring hardcoded
# paths.
#
# The NoDL file content is stored as the resource value so that consumers
# can retrieve it via:
#   ament_index_python.packages.get_resource('nodl_nodes', '<pkg>__<exe>')
#
# Example:
#   ament_nodl_register_node(my_node
#     FILE nodl/my_node.nodl.yaml
#   )
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

  file(READ "${_abs_file}" _nodl_content)

  set(_resource_key "${_ANN_PACKAGE}__${executable_name}")
  set(_marker_dir
    "${CMAKE_CURRENT_BINARY_DIR}/ament_nodl/nodl_nodes")
  file(MAKE_DIRECTORY "${_marker_dir}")
  file(WRITE "${_marker_dir}/${_resource_key}" "${_nodl_content}")

  install(
    FILES "${_marker_dir}/${_resource_key}"
    DESTINATION "share/ament_index/resource_index/nodl_nodes")

  # Also install the source file under the package share directory.
  install(
    FILES "${_abs_file}"
    DESTINATION "share/${_ANN_PACKAGE}/nodl")
endfunction()
