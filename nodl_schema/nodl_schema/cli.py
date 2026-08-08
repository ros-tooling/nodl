# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
import argparse
import sys
from pathlib import Path

from nodl_schema.loader import load_nodl


def main(argv: list[str] | None = None) -> int:
    """``python -m nodl_schema <file>`` -- load and validate a NoDL file.

    Exits 0 on success, 1 on validation failure or I/O error.

    Includes are resolved by default, so validating a document also checks that its references resolve.
    """
    parser = argparse.ArgumentParser(
        prog='python -m nodl_schema',
        description='Validate a NoDL file against the schema.',
    )
    parser.add_argument('file', type=Path, help='Path to the NoDL file to validate.')
    parser.add_argument(
        '--no-resolve',
        dest='resolve',
        action='store_false',
        help='Validate the schema only; do not resolve include references. '
        'By default includes are resolved so the file is checked for resolvability too.',
    )
    args = parser.parse_args(argv)

    try:
        with args.file.open('r') as f:
            load_nodl(f, resolve=args.resolve)
    except Exception as exc:
        print(f'{args.file}: {exc}', file=sys.stderr)
        return 1

    print(f'{args.file}: ok')
    return 0
