# nodl_generate_py(target nodl_file [LIFECYCLE])
#
# Generates an rclpy (or rclpy.lifecycle) base-node class from a NoDL file and
# installs it as an importable Python module.  Unlike the C++ generator there is
# nothing to compile, so this creates a build-time custom target rather than a
# library.
#
# target      - used for the generated class/module name and the
#               generate_parameter_library namespace.
# nodl_file   - path to the .nodl.yaml file (absolute, or relative to the
#               caller's CMakeLists.txt).
# LIFECYCLE   - if set, the generated base inherits
#               rclpy.lifecycle.LifecycleNode.
#
function(nodl_generate_py target nodl_file)
  cmake_parse_arguments(ARG "LIFECYCLE" "" "" ${ARGN})
  if(ARG_UNPARSED_ARGUMENTS)
    message(FATAL_ERROR
      "nodl_generate_py received unknown arguments: ${ARG_UNPARSED_ARGUMENTS}")
  endif()

  get_filename_component(nodl_file_abs "${nodl_file}" ABSOLUTE
    BASE_DIR "${CMAKE_CURRENT_SOURCE_DIR}")

  set(gen_dir "${CMAKE_CURRENT_BINARY_DIR}/nodl_generated/${target}")

  set(lifecycle_arg "")
  if(ARG_LIFECYCLE)
    set(lifecycle_arg "--lifecycle")
  endif()

  set(py_out "${gen_dir}/${target}.py")

  # Make build-time Python dependencies importable by the generator.
  if(DEFINED ENV{PYTHONPATH})
    set(full_pythonpath
      "${_nodl_generator_py_extra_pythonpath}:$ENV{PYTHONPATH}")
  else()
    set(full_pythonpath "${_nodl_generator_py_extra_pythonpath}")
  endif()

  add_custom_command(
    OUTPUT "${py_out}"
    COMMAND ${CMAKE_COMMAND} -E env
      "PYTHONPATH=${full_pythonpath}"
      "${Python3_EXECUTABLE}"
      "${_nodl_generator_py_script}"
      --nodl-file "${nodl_file_abs}"
      --output-dir "${gen_dir}"
      --target-name "${target}"
      --templates-dir "${_nodl_generator_py_templates_dir}"
      ${lifecycle_arg}
    DEPENDS
      "${nodl_file_abs}"
      "${_nodl_generator_py_module}"
      "${_nodl_generator_py_script}"
      "${_nodl_generator_py_templates_dir}/node.py.jinja2"
    COMMENT "nodl_generate_py: generating ${target} from ${nodl_file}"
    VERBATIM
  )

  add_custom_target(${target} ALL DEPENDS "${py_out}"
    COMMENT "Generate ${target} from ${nodl_file}")

  # Install whatever .py the generator emitted (the node module, plus
  # <target>_params.py when the NoDL document declares parameters) as top-level
  # importable modules.
  install(
    DIRECTORY "${gen_dir}/"
    DESTINATION "${PYTHON_INSTALL_DIR}"
    FILES_MATCHING PATTERN "*.py"
  )
endfunction()
