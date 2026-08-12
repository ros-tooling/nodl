# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
import argparse
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    """``python -m nodl_generator_cpp``"""
    parser = argparse.ArgumentParser(
        prog='python -m nodl_generator_cpp',
        description='Generate an rclcpp base-node class from a NoDL document.',
    )
    parser.add_argument('--nodl-file', type=Path, help='Path to the NoDL file to generate from.', required=True)
    parser.add_argument('--output-dir', type=Path, help='Directory to output the .cpp and .hpp files.', required=True)
    parser.add_argument('--target-name', type=str, help='Used for node name.', required=True)
    args = parser.parse_args(argv)

    print('nodl_generator_cpp: not implemented (yet!)')
    print(f'your args: {args}')

    return 0
