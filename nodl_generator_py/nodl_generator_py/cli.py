# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Command-line interface for ``nodl_generator_py``."""

import argparse
import sys
from pathlib import Path

from nodl_generator_py.generator import format_cmake_deps, generate_python, write_generation


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Generate an rclpy base class from a NoDL document.')
    parser.add_argument('--nodl-file', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--target-name', required=True)
    parser.add_argument(
        '--cmake-deps',
        action='store_true',
        help='Write a <target>_deps.cmake file and exit without generating code.',
    )
    args = parser.parse_args(argv)

    try:
        generation = generate_python(args.nodl_file, args.target_name)
        if args.cmake_deps:
            args.output_dir.mkdir(parents=True, exist_ok=True)
            output = args.output_dir / f'{args.target_name}_deps.cmake'
            output.write_text(format_cmake_deps(args.target_name, generation.sources), encoding='utf-8')
            print(f'wrote {output}')
            return 0
        output = write_generation(generation, args.output_dir, args.target_name)
    except Exception as exc:
        print(f'{args.nodl_file}: {exc}', file=sys.stderr)
        return 1

    print(f'wrote {output}')
    return 0
