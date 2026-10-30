# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0

include("${CMAKE_CURRENT_LIST_DIR}/nodl_py_common.cmake")

#
# nodl_add_py_executable(executable target [EXECUTOR ref])
#
# Generate an executable that runs an rclpy node class, and install it to ``lib/<project>``.
#
# The script calls ``nodl_runtime_py.run_node`` on the class,
# which constructs the node, activates it if it is a lifecycle node, and spins it until SIGINT or SIGTERM.
# ``ros2 run <project> <executable>`` runs it.
#
# The calling package must declare ``<exec_depend>nodl_runtime_py</exec_depend>``, which provides ``run_node``.
# The module of the class must be importable from the installed package, for example one installed with ``ament_python_install_package``.
#
# Example::
#
#   nodl_add_py_executable(echo_node my_robot.echo_node:EchoNode)
#
# Spin the node with a different executor::
#
#   nodl_add_py_executable(echo_node my_robot.echo_node:EchoNode
#     EXECUTOR rclpy.executors:MultiThreadedExecutor)
#
# :param executable: name of the installed executable, also used for the build target ``nodl_py_executable_<executable>``.
# :type executable: string
# :param target: ``module:Class`` import reference to the node class.
# :type target: string
# :param EXECUTOR: ``module:Class`` import reference to the executor class that spins the node.
#   Defaults to ``rclpy.executors:SingleThreadedExecutor``.
# :type EXECUTOR: string
#
# @public
#
function(nodl_add_py_executable executable target)
  _nodl_py_require_runtime_dependency(nodl_add_py_executable "the generated executable")

  cmake_parse_arguments(_nodl "" "EXECUTOR" "" ${ARGN})
  if(_nodl_UNPARSED_ARGUMENTS)
    message(FATAL_ERROR
      "nodl_add_py_executable received unknown arguments: ${_nodl_UNPARSED_ARGUMENTS}")
  endif()
  if(_nodl_KEYWORDS_MISSING_VALUES)
    message(FATAL_ERROR
      "nodl_add_py_executable: executable '${executable}' has an EXECUTOR with no value")
  endif()

  set(output "${CMAKE_CURRENT_BINARY_DIR}/nodl_py_executables/${executable}")

  set(executor_args "")
  if(DEFINED _nodl_EXECUTOR)
    set(executor_args --executor "${_nodl_EXECUTOR}")
  endif()

  _nodl_py_generator_command(generator_command nodl_generator_py.executable)

  add_custom_command(
    OUTPUT "${output}"
    COMMAND ${generator_command}
      "${target}"
      ${executor_args}
      --output "${output}"
    DEPENDS "${_nodl_generator_py_package_dir}/executable.py"
    COMMENT "nodl_add_py_executable: generating ${executable} for ${target}"
    VERBATIM
  )

  add_custom_target(nodl_py_executable_${executable} ALL DEPENDS "${output}")

  install(PROGRAMS "${output}" DESTINATION lib/${PROJECT_NAME})
endfunction()
