# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""The shared test helper checks explicit values against a running C++ node."""

import unittest
from pathlib import Path

import pytest

from ros2nodl.conformance import assert_conforms
from ros2nodl.testing import conformance_test

_FIXTURES = Path(__file__).parent / 'fixtures'
_CONTRACT = _FIXTURES / 'conformance_fixture.nodl.yaml'
_NODE = '/parameter_expectations/fixture'

generate_test_description, TestNodlConformance = conformance_test(
    package='test_ament_nodl',
    executable='conformance_fixture_node',
    nodl=_CONTRACT,
    node_name='fixture',
    node_namespace='/parameter_expectations',
    parameters_files=[_FIXTURES / 'conformance_fixture_parameters.yaml'],
)


class TestParameterExpectations(unittest.TestCase):
    def test_unapplied_inline_value_fails(self):
        with pytest.raises(AssertionError, match='value_mismatch'):
            assert_conforms(nodl_file=str(_CONTRACT), node_fqn=_NODE, parameters=['limit:=6'])

    def test_unapplied_file_value_fails(self):
        with pytest.raises(AssertionError, match='value_mismatch'):
            assert_conforms(
                nodl_file=str(_CONTRACT),
                node_fqn=_NODE,
                params_files=[_FIXTURES / 'conformance_fixture_wrong_parameters.yaml'],
            )
