# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
import argparse
import sys
from pathlib import Path

from nodl_generator_cpp.generate import cmake_deps, generate_cpp
from nodl_generator_cpp.params import generate_parameter_header


def main(argv: list[str] | None = None) -> int:
    """``python -m nodl_generator_cpp`` -- generate C++ base-node class from a NoDL file.

    Exits 0 on success, 1 on failure.
    """
    parser = argparse.ArgumentParser(
        prog='python -m nodl_generator_cpp',
        description='Generate an rclcpp base-node class from a NoDL document.',
    )
    parser.add_argument('--nodl-file', type=Path, help='Path to the NoDL file to generate from.', required=True)
    parser.add_argument('--output-dir', type=Path, help='Directory to output the .cpp and .hpp files.', required=True)
    parser.add_argument('--target-name', type=str, help='Used for node name.', required=True)
    parser.add_argument(
        '--cmake-deps',
        action='store_true',
        help='Write a <target>_deps.cmake file and exit without generating code.',
    )
    args = parser.parse_args(argv)

    if args.cmake_deps:
        return _cmake_deps(args)
    return _generate(args)


def _cmake_deps(args: argparse.Namespace) -> int:
    """Write a ``<target>_deps.cmake`` file and exit."""
    try:
        result = cmake_deps(args.nodl_file, args.target_name)
    except Exception as exc:
        print(f'{args.nodl_file}: {exc}', file=sys.stderr)
        return 1

    args.output_dir.mkdir(parents=True, exist_ok=True)
    out_path = args.output_dir / f'{args.target_name}_deps.cmake'
    out_path.write_text(result.format(args.target_name))
    print(f'wrote {out_path}')
    return 0


def _generate(args: argparse.Namespace) -> int:
    """Run the full code generator."""
    try:
        generated_files = generate_cpp(args.nodl_file, args.target_name)
    except Exception as exc:
        print(f'{args.nodl_file}: {exc}', file=sys.stderr)
        return 1

    args.output_dir.mkdir(parents=True, exist_ok=True)
    for gf in generated_files:
        out_path = args.output_dir / gf.filename
        out_path.write_text(gf.content)
        print(f'wrote {out_path}')

    # generate_parameter_library only exposes a file-based interface
    # (no in-memory API), so we must write the YAML first then invoke
    # it on the on-disk file to produce the C++ parameter header.
    # TODO(alistair): contribute a code-level API to genparamlib,
    # or fork the implementation into nodl, so we can avoid this.
    params_yaml = args.output_dir / f'{args.target_name}_parameters.yaml'
    if params_yaml.exists():
        gf = generate_parameter_header(params_yaml)
        out_path = args.output_dir / gf.filename
        out_path.write_text(gf.content)
        print(f'wrote {out_path}')

    return 0
