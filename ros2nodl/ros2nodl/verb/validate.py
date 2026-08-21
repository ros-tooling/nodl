# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""``ros2 nodl validate [files...]`` -- validate NoDL documents against the schema."""

import sys
from pathlib import Path

from jsonschema import ValidationError

from nodl_schema import load_nodl
from ros2nodl.verb import VerbExtension


class ValidateVerb(VerbExtension):
    """Validate NoDL document(s) against the NoDL schema."""

    def add_arguments(self, parser, cli_name):
        parser.add_argument(
            'files',
            type=Path,
            nargs='+',
            help='NoDL files to validate.',
        )
        parser.add_argument(
            '--no-resolve',
            dest='resolve',
            action='store_false',
            help='Validate the schema only; do not resolve include references.',
        )

    def main(self, *, args):
        rc = 0
        for path in args.files:
            rc |= _validate_file(path, resolve=args.resolve)
        return rc


def _validate_file(path: Path, *, resolve: bool = True) -> int:
    try:
        load_nodl(path, resolve=resolve)
    except ValidationError as e:
        chain = ' -> '.join(str(p) for p in e.absolute_path) or '<root>'
        print(f'{path}: INVALID', file=sys.stderr)
        print(f'  {chain}: {e.message}', file=sys.stderr)
        return 1
    except Exception as e:
        print(f'{path}: {e}', file=sys.stderr)
        return 1
    print(f'{path}: ok')
    return 0
