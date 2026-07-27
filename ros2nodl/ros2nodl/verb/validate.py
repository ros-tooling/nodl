# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""``ros2 nodl validate [files...]`` -- validate NoDL documents against the schema."""

import sys

import yaml
from jsonschema import ValidationError

from nodl_schema import validate
from ros2nodl.verb import VerbExtension


class ValidateVerb(VerbExtension):
    """Validate NoDL document(s) against the NoDL schema."""

    def add_arguments(self, parser, cli_name):
        parser.add_argument(
            'files',
            nargs='*',
            help='NoDL files to validate. Reads from stdin if none are given.',
        )

    def main(self, *, args):
        if not args.files:
            return _validate_source(sys.stdin, '<stdin>')

        rc = 0
        for path in args.files:
            try:
                source = open(path, 'r')
            except OSError as e:
                print(f'{path}: {e}', file=sys.stderr)
                rc = 1
                continue
            try:
                rc |= _validate_source(source, path)
            finally:
                source.close()
        return rc


def _validate_source(source, label) -> int:
    try:
        data = yaml.safe_load(source)
        if not isinstance(data, dict):
            raise ValueError('NoDL document must be a YAML/JSON mapping at the top level')
        validate(data)
    except ValidationError as e:
        loc = ' -> '.join(str(p) for p in e.absolute_path) or '<root>'
        print(f'{label}: INVALID', file=sys.stderr)
        print(f'  {loc}: {e.message}', file=sys.stderr)
        return 1
    except Exception as e:
        print(f'{label}: {e}', file=sys.stderr)
        return 1
    print(f'{label}: ok')
    return 0
