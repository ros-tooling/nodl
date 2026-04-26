# nodl_generate_cpp(target nodl_file [LIFECYCLE])
#
# Generates an rclcpp (or rclcpp_lifecycle) base-node class from a NoDL file
# and creates a library target the caller can link against.
#
# target      - CMake target name; used for the generated class name and
#               the generate_parameter_library namespace.
# nodl_file   - Path to the .nodl.yaml file (relative to caller's CMakeLists.txt)
# LIFECYCLE   - If set, the generated base inherits rclcpp_lifecycle::LifecycleNode
#
macro(nodl_generate_cpp target nodl_file)
  cmake_parse_arguments(_NGL "LIFECYCLE" "" "" ${ARGN})

  get_filename_component(_nodl_file_abs "${nodl_file}" ABSOLUTE
    BASE_DIR "${CMAKE_CURRENT_SOURCE_DIR}")

  set(_gen_dir "${CMAKE_CURRENT_BINARY_DIR}/nodl_generated/${target}")
  file(MAKE_DIRECTORY "${_gen_dir}")

  set(_lifecycle_arg "")
  if(_NGL_LIFECYCLE)
    set(_lifecycle_arg "--lifecycle")
  endif()

  set(_hpp_out "${_gen_dir}/${target}.hpp")
  set(_cpp_out "${_gen_dir}/${target}.cpp")

  # Prepend the extra Python paths so generate_parameter_library_py is importable.
  if(DEFINED ENV{PYTHONPATH})
    set(_full_pythonpath "${_NODL_GENERATOR_CPP_EXTRA_PYTHONPATH}:$ENV{PYTHONPATH}")
  else()
    set(_full_pythonpath "${_NODL_GENERATOR_CPP_EXTRA_PYTHONPATH}")
  endif()

  add_custom_command(
    OUTPUT "${_hpp_out}" "${_cpp_out}"
    COMMAND ${CMAKE_COMMAND} -E env
      "PYTHONPATH=${_full_pythonpath}"
      "${Python3_EXECUTABLE}"
      "${_NODL_GENERATOR_CPP_SCRIPT}"
      --nodl-file "${_nodl_file_abs}"
      --output-dir "${_gen_dir}"
      --target-name "${target}"
      --templates-dir "${_NODL_GENERATOR_CPP_TEMPLATES_DIR}"
      ${_lifecycle_arg}
    DEPENDS
      "${_nodl_file_abs}"
      "${_NODL_GENERATOR_CPP_SCRIPT}"
    COMMENT "nodl_generate_cpp: generating ${target} from ${nodl_file}"
    VERBATIM
  )

  add_library(${target} "${_hpp_out}" "${_cpp_out}")
  target_include_directories(${target} PUBLIC
    "$<BUILD_INTERFACE:${_gen_dir}>"
    "$<INSTALL_INTERFACE:include/${target}>"
  )

  # Always link against rclcpp, rclcpp_lifecycle, and the genparamlib runtime
  # deps.  rclcpp_lifecycle is always needed because the generate_parameter_library
  # generated header unconditionally includes lifecycle_node.hpp.
  target_link_libraries(${target} PUBLIC
    rclcpp::rclcpp
    rclcpp_lifecycle::rclcpp_lifecycle
    fmt::fmt
    rsl::rsl
    tcb_span::tcb_span
    tl::expected
    tl_expected::tl_expected
  )
endmacro()
