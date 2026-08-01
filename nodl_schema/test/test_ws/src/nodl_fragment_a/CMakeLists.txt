# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
cmake_minimum_required(VERSION 3.22)
project(nodl_fragment_a)

find_package(ament_cmake REQUIRED)
find_package(nodl_schema REQUIRED)

ament_nodl_install(
  FILES
    nodl/diagnostics.nodl.yaml
    nodl/shared_base.nodl.yaml
    nodl/topic_a.nodl.yaml
    nodl/topic_a_twist.nodl.yaml
    nodl/topic_a_rel_d1.nodl.yaml
    nodl/topic_a_rel_d10.nodl.yaml
    nodl/topic_a_be_d1.nodl.yaml
    nodl/all_endpoints.nodl.yaml
    nodl/speed_v1.nodl.yaml
    nodl/speed_v99.nodl.yaml
    nodl/speed_int.nodl.yaml
    nodl/sub_imu.nodl.yaml
    nodl/srv_set_bool_trigger.nodl.yaml
    nodl/cli_trigger_setbool.nodl.yaml
    nodl/act_navigate_spin.nodl.yaml
    nodl/act_cli_spin_nav.nodl.yaml
    nodl/wraps_topic_a.nodl.yaml
    nodl/wraps_diagnostics.nodl.yaml
    nodl/circular_a.nodl.yaml
)

ament_package()
