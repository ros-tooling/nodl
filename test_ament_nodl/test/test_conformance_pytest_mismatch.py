# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""A node that does not match its document fails the conformance test, which this module checks and does not fail on."""

import unittest
from pathlib import Path

import pytest

from ament_nodl.testing import conformance_test

# Held in a tuple, because launch_testing runs every test case in the module namespace.
_CONFORMANCE = conformance_test(
    package='test_ament_nodl',
    executable='conformance_fixture_node',
    nodl=Path(__file__).parent / 'fixtures' / 'conformance_fixture_mismatch.nodl.yaml',
    node_name='fixture',
    node_namespace='/conformance_pytest_mismatch',
    parameters=['limit:=5', 'mode:=1_000'],
)
generate_test_description = _CONFORMANCE[0]


class TestConformanceMismatch(unittest.TestCase):
    def test_a_mismatched_document_fails(self):
        with pytest.raises(AssertionError, match=r"\[type_mismatch\] publishers '/conformance_pytest_mismatch/state'"):
            _CONFORMANCE[1]('test_conformance').test_conformance()
