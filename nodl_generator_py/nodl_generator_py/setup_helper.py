# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""ament_python build helper for the NoDL rclpy generator."""

from __future__ import annotations

from pathlib import Path

from ament_index_python.packages import get_package_share_directory

from nodl_generator_py.generator import generate


def nodl_generate_py_module(
    nodl_file: str | Path,
    target_name: str,
    output_dir: str | Path,
    *,
    lifecycle: bool = False,
) -> Path:
    """Generate and return the path to ``<target_name>.py``."""
    templates = Path(get_package_share_directory('nodl_generator_py')) / 'templates'
    return generate(
        nodl_file,
        output_dir,
        target_name,
        templates,
        lifecycle=lifecycle,
    )
