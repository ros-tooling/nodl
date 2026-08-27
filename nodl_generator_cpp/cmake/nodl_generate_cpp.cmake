# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
#
# nodl_generate_cpp(TARGET NODL_FILE)
#
# Generate an rclcpp base-node class from a NoDL document and expose it
# as a STATIC library target that the caller can link against.
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
# :param TARGET: Name of the library target to create.  Also used as the
#   C++ class stem (``<TARGET>Base``) and for the generated filenames.
# :type TARGET: string
# :param NODL_FILE: Path to the ``.nodl.yaml`` file, relative to
#   ``CMAKE_CURRENT_SOURCE_DIR``.
# :type NODL_FILE: string
#
# @public
#
macro(nodl_generate_cpp TARGET NODL_FILE)
  # ── paths ───────────────────────────────────────────────────────────
  set(_nodl_file "${CMAKE_CURRENT_SOURCE_DIR}/${NODL_FILE}")
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
    COMMENT "nodl_generate_cpp: ${NODL_FILE} -> ${TARGET}"
    VERBATIM
  )

  # ── create the library target ──────────────────────────────────────
  add_library(${TARGET} STATIC)
  foreach(_f IN LISTS _generated_paths)
    if(_f MATCHES "\\.cpp$")
      target_sources(${TARGET} PRIVATE "${_f}")
    endif()
  endforeach()
  target_include_directories(${TARGET} PUBLIC
    $<BUILD_INTERFACE:${_output_dir}>
  )

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
    # tl_expected::tl_expected (Humble/Jazzy) → tl::expected (Kilted+)
    if(TARGET tl::expected)
      list(APPEND _nodl_genparamlib_deps tl::expected)
    elseif(TARGET tl_expected::tl_expected)
      list(APPEND _nodl_genparamlib_deps tl_expected::tl_expected)
    endif()
    # parameter_traits present in Humble/Jazzy, removed in Kilted+
    if(TARGET parameter_traits::parameter_traits)
      list(APPEND _nodl_genparamlib_deps parameter_traits::parameter_traits)
    endif()
    target_link_libraries(${TARGET} PUBLIC ${_nodl_genparamlib_deps})
  endif()
endmacro()
