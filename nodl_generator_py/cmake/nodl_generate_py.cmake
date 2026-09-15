# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
# nodl_generate_py(target nodl_file)
#
# Generates an rclpy base-node class from a NoDL file and installs it under
# <project>.generated. Unlike the C++ generator there is nothing to compile,
# so this creates a build-time custom target rather than a library.
#
# target      - used directly for the build target, module, and class name.
#               A trailing _base is removed from the runtime node name.
# nodl_file   - path to the .nodl.yaml file (absolute, or relative to the
#               caller's CMakeLists.txt).
#
function(nodl_generate_py target nodl_file)
  if(ARGN)
    message(FATAL_ERROR
      "nodl_generate_py received unknown arguments: ${ARGN}")
  endif()

  get_filename_component(nodl_file_abs "${nodl_file}" ABSOLUTE
    BASE_DIR "${CMAKE_CURRENT_SOURCE_DIR}")

  set(gen_root "${CMAKE_CURRENT_BINARY_DIR}/nodl_generated/${target}")
  set(gen_dir "${gen_root}/${PROJECT_NAME}/generated")

  set(py_out "${gen_dir}/${target}.py")
  set(package_init "${gen_dir}/__init__.py")
  set(params_py "${gen_dir}/${target}_parameters.py")
  set(params_yaml "${gen_dir}/${target}_parameters.yaml")
  set(deps_file "${gen_root}/${target}_deps.cmake")

  # Make build-time Python dependencies importable by the generator.
  if(DEFINED ENV{PYTHONPATH})
    set(full_pythonpath
      "${_nodl_generator_py_extra_pythonpath}:$ENV{PYTHONPATH}")
  else()
    set(full_pythonpath "${_nodl_generator_py_extra_pythonpath}")
  endif()

  # Resolve the include tree during configuration so both configure and build
  # dependencies cover every transitive NoDL input.
  file(MAKE_DIRECTORY "${gen_root}")
  execute_process(
    COMMAND ${CMAKE_COMMAND} -E env
      "PYTHONPATH=${full_pythonpath}"
      "${Python3_EXECUTABLE}"
      -m nodl_generator_py
      --nodl-file "${nodl_file_abs}"
      --output-dir "${gen_root}"
      --target-name "${target}"
      --cmake-deps
    RESULT_VARIABLE nodl_deps_result
  )
  if(NOT nodl_deps_result EQUAL 0)
    message(FATAL_ERROR
      "nodl_generate_py: --cmake-deps failed for target '${target}' "
      "(file: ${nodl_file_abs})")
  endif()
  include("${deps_file}")
  set_property(DIRECTORY APPEND PROPERTY
    CMAKE_CONFIGURE_DEPENDS ${${target}_NODL_SOURCES})

  add_custom_command(
    OUTPUT "${py_out}" "${package_init}"
    BYPRODUCTS "${params_py}" "${params_yaml}"
    COMMAND ${CMAKE_COMMAND} -E env
      "PYTHONPATH=${full_pythonpath}"
      "${Python3_EXECUTABLE}"
      -m nodl_generator_py
      --nodl-file "${nodl_file_abs}"
      --output-dir "${gen_dir}"
      --target-name "${target}"
    COMMAND ${CMAKE_COMMAND} -E touch "${package_init}"
    DEPENDS
      ${${target}_NODL_SOURCES}
      "${_nodl_generator_py_package_dir}/__main__.py"
      "${_nodl_generator_py_package_dir}/cli.py"
      "${_nodl_generator_py_package_dir}/generator.py"
      "${_nodl_generator_py_package_dir}/models.py"
      "${_nodl_generator_py_package_dir}/provenance.py"
      "${_nodl_generator_py_package_dir}/schema.py"
      "${_nodl_generator_py_package_dir}/schemas/codegen_python.schema.yaml"
      "${_nodl_generator_py_package_dir}/templates/node.py.jinja2"
    COMMENT "nodl_generate_py: generating ${target} from ${nodl_file}"
    VERBATIM
  )

  add_custom_target(${target} ALL DEPENDS "${py_out}" "${package_init}"
    COMMENT "Generate ${target} from ${nodl_file}")

  install(
    DIRECTORY "${gen_root}/${PROJECT_NAME}/"
    DESTINATION "${PYTHON_INSTALL_DIR}/${PROJECT_NAME}"
    FILES_MATCHING PATTERN "*.py"
  )
endfunction()
