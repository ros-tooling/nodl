# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Generate the source of an executable that runs an rclpy node class with ``nodl_runtime_py.run_node``.

Usage: ``python3 -m nodl_generator_py.executable TARGET [--executor REF] [--output FILE]``
"""

import argparse
import keyword
import sys
from pathlib import Path

_RESERVED_NAMES = frozenset({'sys', 'run_node'})


def _parse_reference(reference: str, role: str) -> tuple[str, str]:
    """Split a ``module:Class`` import reference into its module and attribute names."""
    module, separator, name = reference.partition(':')
    parts = [*module.split('.'), name]
    if not separator or not all(part.isidentifier() and not keyword.iskeyword(part) for part in parts):
        raise ValueError(f"{role} '{reference}' is not in the form 'module:Class'")
    return module, name


def executable_source(target: str, executor: str | None = None) -> str:
    """Return the source of a Python executable that runs the node class at ``target``.

    :param target: ``module:Class`` import reference to the node class.
    :param executor: ``module:Class`` import reference to the executor class that spins the node,
        such as ``rclpy.executors:MultiThreadedExecutor``.
        By default ``run_node`` uses a ``SingleThreadedExecutor``.
    :return: Script source, starting with a ``#!/usr/bin/env python3`` line.
    :raises ValueError: If a reference is malformed, or its class name collides with another name in the script.
    """
    references = [('Node target', target)] + ([('Executor', executor)] if executor is not None else [])
    parsed = [(role, *_parse_reference(reference, role)) for role, reference in references]
    names = [name for _, _, name in parsed]
    if len(set(names)) != len(names) or _RESERVED_NAMES.intersection(names):
        raise ValueError(f'Class names {names} must be distinct and must not be any of {sorted(_RESERVED_NAMES)}')

    imports = ''.join(f'from {module} import {name}\n' for _, module, name in parsed)
    run_arguments = names[0] if executor is None else f'{names[0]}, executor_class={names[1]}'
    return (
        '#!/usr/bin/env python3\n'
        'import sys\n'
        '\n'
        'from nodl_runtime_py import run_node\n'
        f'{imports}'
        '\n'
        f'sys.exit(run_node({run_arguments}))\n'
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description='Generate an executable that runs an rclpy node class with nodl_runtime_py.run_node.'
    )
    parser.add_argument('target', help='module:Class import reference to the node class')
    parser.add_argument(
        '--executor',
        help='module:Class import reference to the executor class, for example rclpy.executors:MultiThreadedExecutor',
    )
    parser.add_argument('--output', type=Path, help='write an executable file instead of printing the source')
    args = parser.parse_args(argv)

    try:
        source = executable_source(args.target, args.executor)
    except ValueError as exc:
        print(f'{parser.prog}: {exc}', file=sys.stderr)
        return 1

    if args.output is None:
        sys.stdout.write(source)
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(source, encoding='utf-8')
    args.output.chmod(0o755)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
