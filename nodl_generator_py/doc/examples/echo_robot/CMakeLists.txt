# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
cmake_minimum_required(VERSION 3.22)
project(echo_robot)

find_package(ament_cmake REQUIRED)
find_package(ament_cmake_python REQUIRED)
find_package(nodl_generator_py REQUIRED)

ament_python_install_package(${PROJECT_NAME})

nodl_generate_py(echo_node_base nodl/echo_node.nodl.yaml)

nodl_add_py_executable(echo_node echo_robot.echo_node:EchoNode)

ament_package()
