# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
ament_nodl_register(subdir_node FILE subdir_node.nodl.yaml)
# Same source file name as test/fixtures/basic_node.nodl.yaml, registered under a different resource name.
ament_nodl_register(subdir_basic_node FILE basic_node.nodl.yaml)
