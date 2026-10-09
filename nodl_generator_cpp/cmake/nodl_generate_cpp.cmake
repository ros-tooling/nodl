# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0

#
# nodl_generate_cpp(TARGET [SHARED|STATIC] [EXPORT] [NO_INDEX] [RESOURCE_NAME name] NODL_FILE)
#
# Generate an rclcpp base-node class from a NoDL document and expose it
# as a library target that the caller can link against.
# The library type follows ``BUILD_SHARED_LIBS``, like ``add_library``.
# ``BUILD_SHARED_LIBS`` is unset unless the package sets it,
# for example with ``option(BUILD_SHARED_LIBS "Build shared libraries" ON)``,
# or finds ``ament_cmake_ros``, which enables it.
# Without it the libraries are STATIC.
# ``SHARED`` or ``STATIC`` overrides it.
# Giving both is an error.
# Both types are built as position-independent code, so a STATIC library
# can be linked into a SHARED library.
# SHARED libraries are installed to ``lib`` (``bin`` for DLLs), which is on
# the library path of a sourced workspace.
# STATIC libraries are not installed unless they are exported, because an archive has no runtime role.
# The library file is named after ``<PROJECT_NAME>_<TARGET>``,
# for example ``lib<PROJECT_NAME>_<TARGET>.so``,
# to avoid collisions between packages in a shared install space.
# The CMake target name remains ``TARGET``.
# A target that already starts with the package name gets it twice,
# so target ``my_pkg_base`` in project ``my_pkg`` produces ``libmy_pkg_my_pkg_base.so``.
#
# A library is private to the package unless ``EXPORT`` is given.
# ``EXPORT`` applies to both types, and installs the headers so that other packages can use the library.
# Downstream packages may then call ``find_package(<project>)``, link ``<project>::<TARGET>``, and ``#include <project>/<target>.hpp``.
# An exported library must be created before ``ament_package()``, in the same CMakeLists.txt, not inside a function or subdirectory.
# Doing so raises an error.
# The exporting package declares ``nodl_generator_cpp`` as a ``<buildtool_export_depend>``,
# and the ROS dependencies of its documents as ``<depend>`` or ``<build_export_depend>``.
# A STATIC library linked into several SHARED libraries that are loaded into one process
# gives each of them its own copy of the class and parameter code.
#
# The same call registers the document with the ament index,
# so the node's interface is discoverable as ``nodl://<project>/<name>``.
# The name is ``TARGET`` unless ``RESOURCE_NAME`` overrides it.
# Renaming the target renames the registered resource, unless ``RESOURCE_NAME`` is set.
# The full document is registered as written, including any ``codegen`` block.
# Use ``NO_INDEX`` to skip registration.
# Giving ``RESOURCE_NAME`` together with ``NO_INDEX`` is an error.
# Each resource name and each document file can be registered once per package.
# Every ``local://`` include of the document must be registered in this package with ``ament_nodl_register``, or configuration fails.
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
# The generated header is included by its package-scoped path::
#
#   #include "<project>/my_node_base.hpp"
#
# Request a static library regardless of ``BUILD_SHARED_LIBS``::
#
#   nodl_generate_cpp(my_node_base STATIC my_node.nodl.yaml)
#
# Skip index registration::
#
#   nodl_generate_cpp(my_node_base NO_INDEX my_node.nodl.yaml)
#
# Register under a name other than the target::
#
#   nodl_generate_cpp(my_node_base RESOURCE_NAME my_node my_node.nodl.yaml)
#
# Export the library for other packages::
#
#   nodl_generate_cpp(my_node_base EXPORT my_node.nodl.yaml)
#
# A downstream package links the exported target::
#
#   find_package(my_pkg REQUIRED)
#   target_link_libraries(downstream_library PRIVATE my_pkg::my_node_base)
#
# :param TARGET: Name of the library target to create.  Used verbatim as
#   the C++ class name (PascalCased) and for the generated filenames, so a
#   ``<node>_base`` target yields a ``<Node>Base`` class.  A single trailing
#   ``_base`` is stripped to form the runtime node name.
# :type TARGET: string
# :param SHARED: Build a SHARED library, whatever ``BUILD_SHARED_LIBS`` says.
# :param STATIC: Build a STATIC library, whatever ``BUILD_SHARED_LIBS`` says.
# :param EXPORT: Install the headers and export the target to downstream packages.
#   Without it, a SHARED library is only installed to ``lib`` for use by executables at runtime,
#   and a STATIC library is not installed at all.
# :param NO_INDEX: Do not register the document with the ament index.
# :param RESOURCE_NAME: Name to register the document under.
#   Defaults to ``TARGET``.  An error together with ``NO_INDEX``.
# :type RESOURCE_NAME: string
# :param NODL_FILE: Path to the ``.nodl.yaml`` file, relative to
#   ``CMAKE_CURRENT_SOURCE_DIR``.
# :type NODL_FILE: string
#
# @public
#
macro(nodl_generate_cpp TARGET)
  # ── argument parsing ───────────────────────────────────────────────
  cmake_parse_arguments(_nodl "SHARED;STATIC;EXPORT;NO_INDEX" "RESOURCE_NAME" "" ${ARGN})
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
  if(_nodl_KEYWORDS_MISSING_VALUES)
    message(FATAL_ERROR
      "nodl_generate_cpp: target '${TARGET}' has a RESOURCE_NAME with no value")
  endif()
  # A name such as "off" or "0" is a valid value, so test for presence rather than truthiness.
  if(DEFINED _nodl_RESOURCE_NAME)
    set(_nodl_has_resource_name TRUE)
    set(_nodl_resource_name "${_nodl_RESOURCE_NAME}")
  else()
    set(_nodl_has_resource_name FALSE)
    set(_nodl_resource_name "${TARGET}")
  endif()
  if(_nodl_NO_INDEX AND _nodl_has_resource_name)
    message(FATAL_ERROR
      "nodl_generate_cpp: target '${TARGET}' is not registered with the ament index because of NO_INDEX, "
      "so RESOURCE_NAME '${_nodl_RESOURCE_NAME}' has no effect. "
      "Remove one of them.")
  endif()
  set(_nodl_file_arg "${_nodl_UNPARSED_ARGUMENTS}")
  # An empty type lets add_library follow BUILD_SHARED_LIBS.
  set(_nodl_library_type "")
  if(_nodl_SHARED)
    set(_nodl_library_type SHARED)
  elseif(_nodl_STATIC)
    set(_nodl_library_type STATIC)
  endif()
  # The library type does not affect the export.
  set(_nodl_exported ${_nodl_EXPORT})
  if(_nodl_exported)
    # ament_export_* records state in variables of the calling scope,
    # so calling in function or subdirectory would silently lose the export.
    # Script mode has no project, so PROJECT_SOURCE_DIR is empty there.
    if(DEFINED CMAKE_CURRENT_FUNCTION)
      message(FATAL_ERROR
        "nodl_generate_cpp: target '${TARGET}' is exported, so it cannot be created inside function '${CMAKE_CURRENT_FUNCTION}'. "
        "Turn the function into a macro, or call it from the CMakeLists.txt that calls ament_package().")
    elseif(PROJECT_SOURCE_DIR AND NOT CMAKE_CURRENT_SOURCE_DIR STREQUAL PROJECT_SOURCE_DIR)
      message(FATAL_ERROR
        "nodl_generate_cpp: target '${TARGET}' is exported, so it cannot be created in subdirectory '${CMAKE_CURRENT_SOURCE_DIR}'. "
        "Call it from the CMakeLists.txt that calls ament_package().")
    endif()
  endif()

  # ── paths ───────────────────────────────────────────────────────────
  set(_nodl_file "${CMAKE_CURRENT_SOURCE_DIR}/${_nodl_file_arg}")
  set(_output_dir "${CMAKE_CURRENT_BINARY_DIR}/nodl_generated/${TARGET}")
  set(_deps_file "${_output_dir}/${TARGET}_deps.cmake")
  set(_nodl_include_prefix "${PROJECT_NAME}")

  # ── configure-time: emit deps ──────────────────────────────────────
  # Runs the generator in --cmake-deps mode which writes a small CMake
  # file containing NODL_SOURCES, ROS_DEPS, and GENERATED_FILES.
  file(MAKE_DIRECTORY "${_output_dir}")
  execute_process(
    COMMAND "${Python3_EXECUTABLE}" -m nodl_generator_cpp
      --nodl-file "${_nodl_file}"
      --output-dir "${_output_dir}"
      --target-name "${TARGET}"
      --include-prefix "${_nodl_include_prefix}"
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
      --include-prefix "${_nodl_include_prefix}"
    DEPENDS ${${TARGET}_NODL_SOURCES}
    COMMENT "nodl_generate_cpp: ${_nodl_file_arg} -> ${TARGET}"
    VERBATIM
  )

  # ── create the library target ──────────────────────────────────────
  add_library(${TARGET} ${_nodl_library_type})
  get_target_property(_nodl_actual_type ${TARGET} TYPE)
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
  set_target_properties(${TARGET} PROPERTIES OUTPUT_NAME "${PROJECT_NAME}_${TARGET}")
  if(_nodl_actual_type STREQUAL "SHARED_LIBRARY")
    # The generated code has no export macros.
    set_target_properties(${TARGET} PROPERTIES WINDOWS_EXPORT_ALL_SYMBOLS ON)
  endif()
  # A STATIC library has no runtime role, so it is only installed when it is exported.
  if(_nodl_exported OR _nodl_actual_type STREQUAL "SHARED_LIBRARY")
    set(_nodl_export_args "")
    if(_nodl_exported)
      set(_nodl_export_args
        EXPORT export_${TARGET}
        INCLUDES DESTINATION include/${PROJECT_NAME})
    endif()
    install(TARGETS ${TARGET} ${_nodl_export_args}
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
  # The extras of nodl_generator_cpp have already found the package.
  # Target names changed across distros, so we use if(TARGET) guards.
  list(FIND ${TARGET}_GENERATED_FILES "${TARGET}_parameters.yaml" _has_params_idx)
  if(NOT _has_params_idx EQUAL -1)
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

  # ── ament index registration ───────────────────────────────────────
  if(NOT _nodl_NO_INDEX)
    ament_nodl_register(${_nodl_resource_name} FILE "${_nodl_file}")
  endif()

  # ── export for downstream packages ─────────────────────────────────
  if(_nodl_exported)
    # Its extras find the parameter library, with the packages that a parameterized target links.
    set(_nodl_export_deps ${${TARGET}_ROS_DEPS} nodl_generator_cpp)
    list(REMOVE_DUPLICATES _nodl_export_deps)
    set(_nodl_export_headers "")
    foreach(_f IN LISTS ${TARGET}_GENERATED_FILES)
      if(_f MATCHES "\\.hpp$")
        list(APPEND _nodl_export_headers "${_f}")
      endif()
    endforeach()
    _nodl_cpp_export(${TARGET}
      OUTPUT_DIR "${_output_dir}"
      HEADERS ${_nodl_export_headers}
      DEPENDENCIES ${_nodl_export_deps})
  endif()
endmacro()

# Install the generated headers and register the export set of a target.
# HEADERS are relative to OUTPUT_DIR and keep that layout under ``include/${PROJECT_NAME}``.
# This is a macro because ament_export_* record their state in the calling scope.
macro(_nodl_cpp_export TARGET)
  cmake_parse_arguments(_nodl_export "" "OUTPUT_DIR" "HEADERS;DEPENDENCIES" ${ARGN})
  foreach(_h IN LISTS _nodl_export_HEADERS)
    get_filename_component(_h_dir "${_h}" DIRECTORY)
    install(FILES "${_nodl_export_OUTPUT_DIR}/${_h}"
      DESTINATION "include/${PROJECT_NAME}/${_h_dir}")
  endforeach()
  ament_export_targets(export_${TARGET} HAS_LIBRARY_TARGET)
  ament_export_dependencies(${_nodl_export_DEPENDENCIES})
endmacro()
