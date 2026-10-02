# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0

#
# nodl_generate_cpp(TARGET [SHARED|STATIC] NODL_FILE)
#
# Generate an rclcpp base-node class from a NoDL document and expose it
# as a library target that the caller can link against.
# The library is SHARED by default, or STATIC when requested.
# Giving both SHARED and STATIC is an error.
# The library type does not follow ``BUILD_SHARED_LIBS``.
# Both types are built as position-independent code, so a STATIC library
# can be linked into a SHARED library.
# SHARED libraries are installed to ``lib`` (``bin`` for DLLs), which is on
# the library path of a sourced workspace.
#
# Example::
#
#   find_package(nodl_generator_cpp REQUIRED)
#
#   nodl_generate_cpp(my_node_base my_node.nodl.yaml)
#
#   add_executable(my_node src/my_node.cpp)
#   target_link_libraries(my_node PRIVATE my_node_base)
#
# Request a static library explicitly::
#
#   nodl_generate_cpp(my_node_base STATIC my_node.nodl.yaml)
#
# :param TARGET: Name of the library target to create.  Used verbatim as
#   the C++ class name (PascalCased) and for the generated filenames, so a
#   ``<node>_base`` target yields a ``<Node>Base`` class.  A single trailing
#   ``_base`` is stripped to form the runtime node name.
# :type TARGET: string
# :param SHARED: Build a SHARED library.  This is the default, installed to ``lib``.
# :param STATIC: Build a STATIC library.  It is not installed.
# :param NODL_FILE: Path to the ``.nodl.yaml`` file, relative to
#   ``CMAKE_CURRENT_SOURCE_DIR``.
# :type NODL_FILE: string
#
# @public
#
macro(nodl_generate_cpp TARGET)
  # ── argument parsing ───────────────────────────────────────────────
  cmake_parse_arguments(_nodl "SHARED;STATIC" "" "" ${ARGN})
  if(_nodl_SHARED AND _nodl_STATIC)
    message(FATAL_ERROR
      "nodl_generate_cpp: target '${TARGET}' cannot be both SHARED and STATIC")
  endif()
  list(LENGTH _nodl_UNPARSED_ARGUMENTS _nodl_unparsed_count)
  if(NOT _nodl_unparsed_count EQUAL 1)
    message(FATAL_ERROR
      "nodl_generate_cpp: target '${TARGET}' requires exactly one NODL_FILE, "
      "got ${_nodl_unparsed_count}: '${_nodl_UNPARSED_ARGUMENTS}'")
  endif()
  set(_nodl_file_arg "${_nodl_UNPARSED_ARGUMENTS}")
  if(_nodl_STATIC)
    set(_nodl_library_type STATIC)
  else()
    set(_nodl_library_type SHARED)
  endif()

  # ── paths ───────────────────────────────────────────────────────────
  set(_nodl_file "${CMAKE_CURRENT_SOURCE_DIR}/${_nodl_file_arg}")
  set(_output_dir "${CMAKE_CURRENT_BINARY_DIR}/nodl_generated/${TARGET}")
  set(_deps_file "${_output_dir}/${TARGET}_deps.cmake")

  # ── configure-time: emit deps ──────────────────────────────────────
  # Runs the generator in --cmake-deps mode which writes a small CMake
  # file containing NODL_SOURCES, ROS_DEPS, and GENERATED_FILES.
  file(MAKE_DIRECTORY "${_output_dir}")
  execute_process(
    COMMAND "${Python3_EXECUTABLE}" -m nodl_generator_cpp
      --nodl-file "${_nodl_file}"
      --output-dir "${_output_dir}"
      --target-name "${TARGET}"
      --cmake-deps
    RESULT_VARIABLE _nodl_result
  )
  if(NOT _nodl_result EQUAL 0)
    message(FATAL_ERROR
      "nodl_generate_cpp: --cmake-deps failed for target '${TARGET}' "
      "(file: ${_nodl_file})")
  endif()
  include("${_deps_file}")

  # ── watch all NoDL sources for reconfigure ─────────────────────────
  # Every file in the include tree is a configure-dependency.  Any
  # change to the root or any transitive include triggers a reconfigure
  # so the deps file is always up to date.
  set_property(DIRECTORY APPEND PROPERTY
    CMAKE_CONFIGURE_DEPENDS ${${TARGET}_NODL_SOURCES})

  # ── find_package for ROS dependencies ──────────────────────────────
  foreach(_dep IN LISTS ${TARGET}_ROS_DEPS)
    find_package(${_dep} REQUIRED)
  endforeach()

  # ── build-time: code generation ────────────────────────────────────
  # Prepend the output directory to each generated filename so CMake
  # can track them as concrete build products.
  set(_generated_paths "")
  foreach(_f IN LISTS ${TARGET}_GENERATED_FILES)
    list(APPEND _generated_paths "${_output_dir}/${_f}")
  endforeach()

  add_custom_command(
    OUTPUT ${_generated_paths}
    COMMAND "${Python3_EXECUTABLE}" -m nodl_generator_cpp
      --nodl-file "${_nodl_file}"
      --output-dir "${_output_dir}"
      --target-name "${TARGET}"
    DEPENDS ${${TARGET}_NODL_SOURCES}
    COMMENT "nodl_generate_cpp: ${_nodl_file_arg} -> ${TARGET}"
    VERBATIM
  )

  # ── create the library target ──────────────────────────────────────
  add_library(${TARGET} ${_nodl_library_type})
  foreach(_f IN LISTS _generated_paths)
    if(_f MATCHES "\\.cpp$")
      target_sources(${TARGET} PRIVATE "${_f}")
    endif()
  endforeach()
  target_include_directories(${TARGET} PUBLIC
    $<BUILD_INTERFACE:${_output_dir}>
  )
  # PIC lets a STATIC library link into a SHARED one.
  set_target_properties(${TARGET} PROPERTIES POSITION_INDEPENDENT_CODE ON)
  if(_nodl_library_type STREQUAL "SHARED")
    # The generated code has no export macros.
    set_target_properties(${TARGET} PROPERTIES WINDOWS_EXPORT_ALL_SYMBOLS ON)
    install(TARGETS ${TARGET}
      ARCHIVE DESTINATION lib
      LIBRARY DESTINATION lib
      RUNTIME DESTINATION bin
    )
  endif()

  # ── wire up ROS dependencies ────────────────────────────────────────
  # ${pkg_TARGETS} is available since Foxy and works across all
  # supported distros (Humble → Lyrical), unlike ament_target_dependencies
  # which was removed in Lyrical.
  foreach(_dep IN LISTS ${TARGET}_ROS_DEPS)
    target_link_libraries(${TARGET} PUBLIC ${${_dep}_TARGETS})
  endforeach()

  # ── generate_parameter_library dependencies (when params present) ──
  # The generated parameter header (from generate_parameter_library_py)
  # includes fmt, rsl, etc.  Mirror the same link set that
  # generate_parameter_library's own CMake macro uses.
  # Target names changed across distros, so we use if(TARGET) guards.
  list(FIND ${TARGET}_GENERATED_FILES "${TARGET}_parameters.hpp" _has_params_idx)
  if(NOT _has_params_idx EQUAL -1)
    find_package(generate_parameter_library REQUIRED)
    set(_nodl_genparamlib_deps
      fmt::fmt
      rclcpp::rclcpp
      rclcpp_lifecycle::rclcpp_lifecycle
      rsl::rsl
      tcb_span::tcb_span
    )
    # tl_expected::tl_expected (Humble/Jazzy) → tl::expected (Lyrical+)
    if(TARGET tl::expected)
      list(APPEND _nodl_genparamlib_deps tl::expected)
    elseif(TARGET tl_expected::tl_expected)
      list(APPEND _nodl_genparamlib_deps tl_expected::tl_expected)
    endif()
    # parameter_traits present in Humble/Jazzy, removed in Lyrical+
    if(TARGET parameter_traits::parameter_traits)
      list(APPEND _nodl_genparamlib_deps parameter_traits::parameter_traits)
    endif()
    target_link_libraries(${TARGET} PUBLIC ${_nodl_genparamlib_deps})
  endif()
endmacro()
