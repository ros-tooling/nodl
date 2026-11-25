# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""A lifecycle node that fails to configure fails the conformance test, which this module checks and does not fail on."""

import unittest
from pathlib import Path

import pytest

from ros2nodl.testing import conformance_test

# Held in a tuple, because launch_testing runs every test case in the module namespace.
_CONFORMANCE = conformance_test(
    package='test_ament_nodl',
    executable='conformance_lifecycle_failing_node',
    nodl=Path(__file__).parent / 'fixtures' / 'conformance_lifecycle.nodl.yaml',
    node_name='lifecycle_fixture',
    node_namespace='/conformance_lifecycle_failure',
)
generate_test_description = _CONFORMANCE[0]


class TestLifecycleFailure(unittest.TestCase):
    def test_a_failed_configure_fails_the_test(self):
        with pytest.raises(
            AssertionError,
            match='/conformance_lifecycle_failure/lifecycle_fixture: the configure transition failed, and the node is unconfigured',
        ):
            getattr(_CONFORMANCE[1]('test_conformance'), 'test_conformance')()
