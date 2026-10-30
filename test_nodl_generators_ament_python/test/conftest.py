# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Make the tests import the built package, which has the generated modules, rather than the source package, which has none."""

import os
import sys
from pathlib import Path

import pytest
import rclpy

PACKAGE = 'test_nodl_generators_ament_python'
SOURCE_ROOT = Path(__file__).resolve().parent.parent

# `python -m pytest` in the package directory, as colcon runs it, puts the source package first on the path.
# The source package has no generated modules, so the tests import the built package instead.
sys.path[:] = [entry for entry in sys.path if Path(entry or '.').resolve() != SOURCE_ROOT]

# Other packages' tests run at the same time, and some use the same topic names.
os.environ['ROS_DOMAIN_ID'] = str(os.getpid() % 100 + 100)


@pytest.fixture
def ros_context():
    rclpy.init()
    try:
        yield
    finally:
        rclpy.shutdown()
