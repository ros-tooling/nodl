# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0

# Private helpers shared by the public functions of this package.

#
# _nodl_py_require_runtime_dependency(caller needed_by)
#
# Fail configuration unless the calling package declares a runtime dependency on ``nodl_runtime_py``.
#
# :param caller: name of the public function to name in the error message.
# :type caller: string
# :param needed_by: what imports ``nodl_runtime_py`` when it runs, for the error message.
# :type needed_by: string
#
function(_nodl_py_require_runtime_dependency caller needed_by)
  if(NOT DEFINED _AMENT_PACKAGE_NAME)
    ament_package_xml()
  endif()
  if(NOT "nodl_runtime_py" IN_LIST ${PROJECT_NAME}_EXEC_DEPENDS)
    message(FATAL_ERROR
      "${caller}: package '${PROJECT_NAME}' must declare a runtime dependency on nodl_runtime_py, "
      "which ${needed_by} needs when it runs. "
      "Add <exec_depend>nodl_runtime_py</exec_depend> to its package.xml.")
  endif()
endfunction()

#
# _nodl_py_generator_command(output_variable module)
#
# Set a variable to the command prefix that runs a module of ``nodl_generator_py``,
# with the build-time Python dependencies of the generator importable.
#
# :param output_variable: variable to set, in the caller's scope, to a CMake list, so its elements must not contain ``;``.
# :type output_variable: string
# :param module: module to run, such as ``nodl_generator_py`` or ``nodl_generator_py.executable``.
# :type module: string
#
function(_nodl_py_generator_command output_variable module)
  if(DEFINED ENV{PYTHONPATH})
    set(pythonpath "${_nodl_generator_py_extra_pythonpath}:$ENV{PYTHONPATH}")
  else()
    set(pythonpath "${_nodl_generator_py_extra_pythonpath}")
  endif()
  set(${output_variable}
    ${CMAKE_COMMAND} -E env "PYTHONPATH=${pythonpath}" "${Python3_EXECUTABLE}" -m ${module}
    PARENT_SCOPE)
endfunction()
