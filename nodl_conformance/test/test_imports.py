# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Dependency-boundary tests for the pure comparison package."""

import subprocess
import sys


def test_public_package_does_not_import_runtime_or_launch_packages():
    script = """
import sys
import nodl_conformance

blocked = ('ros2nodl', 'launch', 'launch_ros', 'launch_testing', 'rclpy')
assert nodl_conformance.__all__ == ['Difference', 'diff']
assert not any(
    name == prefix or name.startswith(f'{prefix}.')
    for prefix in blocked
    for name in sys.modules
)
"""

    subprocess.run([sys.executable, '-c', script], check=True)
