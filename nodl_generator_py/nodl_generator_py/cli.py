# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Command-line interface for ``nodl_generator_py``."""

import argparse
import sys
from pathlib import Path

from nodl_generator_py.generator import format_cmake_deps, generate_python

VALIDATORS_IMPORT = 'from generate_parameter_library_py.python_validators import ParameterValidators'


def write_parameters_module(output_dir: Path, target_name: str, parameters_yaml: str) -> None:
    """Write the parameter module with a private copy of the validators it uses.

    ``generate_parameter_library_py`` emits a module that imports its validators at runtime.
    Installing a copy beside the module keeps the generated code free of build-time packages,
    so a package that generates nodes needs ``nodl_generator_py`` only as a build tool.
    """
    from generate_parameter_library_py import python_validators
    from generate_parameter_library_py.generate_python_module import run

    parameters_input = output_dir / f'{target_name}_parameters.yaml'
    parameters_input.write_text(parameters_yaml, encoding='utf-8')
    parameters_module = output_dir / f'{target_name}_parameters.py'
    run(str(parameters_module), str(parameters_input), validation_module='')

    validators = f'{target_name}_parameter_validators'
    code = parameters_module.read_text(encoding='utf-8')
    if VALIDATORS_IMPORT not in code:
        raise RuntimeError(f'{parameters_module} does not import the validators as expected: {VALIDATORS_IMPORT!r}')
    parameters_module.write_text(
        code.replace(VALIDATORS_IMPORT, f'from .{validators} import ParameterValidators'), encoding='utf-8'
    )
    (output_dir / f'{validators}.py').write_text(
        Path(python_validators.__file__).read_text(encoding='utf-8'), encoding='utf-8'
    )


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
        args.output_dir.mkdir(parents=True, exist_ok=True)
        if args.cmake_deps:
            output = args.output_dir / f'{args.target_name}_deps.cmake'
            output.write_text(format_cmake_deps(args.target_name, generation.sources), encoding='utf-8')
            print(f'wrote {output}')
            return 0
        output = args.output_dir / f'{args.target_name}.py'
        output.write_text(generation.module, encoding='utf-8')
        if generation.parameters_yaml is not None:
            write_parameters_module(args.output_dir, args.target_name, generation.parameters_yaml)
    except Exception as exc:
        print(f'{args.nodl_file}: {exc}', file=sys.stderr)
        return 1

    print(f'wrote {output}')
    return 0
