# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
# test_ament_nodl runs this file by its path in the source tree, so it stays tested while the docs include it.
from ament_nodl.testing import conformance_test

generate_test_description, TestNodlConformance = conformance_test(
    package='test_ament_nodl',
    executable='conformance_fixture_node',
    nodl='nodl://test_ament_nodl/conformance_fixture',
    node_namespace='/conformance_pytest',
    parameters=['limit:=5', 'mode:=1_000'],
)
