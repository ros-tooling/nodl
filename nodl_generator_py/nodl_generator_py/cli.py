# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Command-line interface for ``nodl_generator_py``."""

import argparse
import sys
from pathlib import Path

from nodl_generator_py.generator import generate_parameter_yaml, generate_python
from nodl_schema import load_nodl


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Generate an rclpy base class from a NoDL document.')
    parser.add_argument('--nodl-file', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--target-name', required=True)
    args = parser.parse_args(argv)

    try:
        doc = load_nodl(args.nodl_file, resolve=False)
        generated = generate_python(doc, args.target_name)
        parameters_yaml = generate_parameter_yaml(doc, args.target_name)
        args.output_dir.mkdir(parents=True, exist_ok=True)
        output = args.output_dir / f'{args.target_name}.py'
        output.write_text(generated, encoding='utf-8')
        if parameters_yaml is not None:
            from generate_parameter_library_py.generate_python_module import run

            parameters_input = args.output_dir / f'{args.target_name}_params.yaml'
            parameters_input.write_text(parameters_yaml, encoding='utf-8')
            run(
                str(args.output_dir / f'{args.target_name}_params.py'),
                str(parameters_input),
                validation_module='',
            )
    except Exception as exc:
        print(f'{args.nodl_file}: {exc}', file=sys.stderr)
        return 1

    print(f'wrote {output}')
    return 0
