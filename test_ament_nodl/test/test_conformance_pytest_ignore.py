# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""A node with an endpoint its document does not declare conforms through ``ignore``, with a document path and a parameters file."""

from pathlib import Path

from ament_nodl.testing import conformance_test

_FIXTURES = Path(__file__).parent / 'fixtures'

generate_test_description, TestNodlConformance = conformance_test(
    package='test_ament_nodl',
    executable='conformance_injected_node',
    nodl=_FIXTURES / 'conformance_fixture.nodl.yaml',
    node_name='fixture',
    node_namespace='/conformance_pytest_ignore',
    parameters_files=[_FIXTURES / 'conformance_fixture_parameters.yaml'],
    ignore=['publisher:/topic_statistics'],
)
