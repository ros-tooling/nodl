# nodl_docgen(target nodl_file)
#
# Generates an RST documentation file from a NoDL interface description.
#
# target      - Name for the cmake custom target; also used as the output filename
#               (<target>.rst).
# nodl_file   - Path to the .nodl.yaml file (relative to caller's CMakeLists.txt).
#
# The generated RST is placed in ${CMAKE_CURRENT_BINARY_DIR}/nodl_doc/<target>.rst
# and installed to share/<package>/doc/.
#
# Example:
#   nodl_docgen(my_node nodl/my_node.nodl.yaml)
#   # Produces: share/<package>/doc/my_node.rst
#   # Include in your Sphinx docs with:
#   #   .. include:: /path/to/install/share/<package>/doc/my_node.rst
#   # Or add to toctree.
#
macro(nodl_docgen target nodl_file)
  get_filename_component(_nodl_file_abs "${nodl_file}" ABSOLUTE
    BASE_DIR "${CMAKE_CURRENT_SOURCE_DIR}")

  set(_out_dir "${CMAKE_CURRENT_BINARY_DIR}/nodl_doc")
  set(_rst_out "${_out_dir}/${target}.rst")

  if(DEFINED ENV{PYTHONPATH})
    set(_full_pythonpath "${_NODL_DOCGEN_EXTRA_PYTHONPATH}:$ENV{PYTHONPATH}")
  else()
    set(_full_pythonpath "${_NODL_DOCGEN_EXTRA_PYTHONPATH}")
  endif()

  add_custom_command(
    OUTPUT "${_rst_out}"
    COMMAND ${CMAKE_COMMAND} -E make_directory "${_out_dir}"
    COMMAND ${CMAKE_COMMAND} -E env
      "PYTHONPATH=${_full_pythonpath}"
      "${Python3_EXECUTABLE}"
      "${_NODL_DOCGEN_SCRIPT}"
      --nodl-file "${_nodl_file_abs}"
      --output "${_rst_out}"
    DEPENDS
      "${_nodl_file_abs}"
      "${_NODL_DOCGEN_SCRIPT}"
    COMMENT "nodl_docgen: generating ${target}.rst from ${nodl_file}"
    VERBATIM
  )

  add_custom_target(${target}_nodl_doc ALL DEPENDS "${_rst_out}")

  if(DEFINED PROJECT_NAME)
    install(
      FILES "${_rst_out}"
      DESTINATION share/${PROJECT_NAME}/doc
      OPTIONAL
    )
  endif()
endmacro()
