# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""``ros2 nodl diff`` -- compare two NoDL documents semantically."""

import sys
from pathlib import Path

from nodl_schema import diff, load_nodl
from ros2nodl.verb import VerbExtension

_DEFAULT_NODE_NAME = '/node'


class DiffVerb(VerbExtension):
    """Compare two NoDL documents without observing a running node."""

    def add_arguments(self, parser, cli_name):
        parser.add_argument('expected', type=Path, metavar='EXPECTED', help='Expected NoDL document.')
        parser.add_argument('actual', type=Path, metavar='ACTUAL', help='Actual NoDL document.')
        parser.add_argument(
            '--node-name',
            default=_DEFAULT_NODE_NAME,
            metavar='NODE_NAME',
            help='Fully-qualified node name used to resolve relative interface names (default: %(default)s).',
        )

    def main(self, *, args) -> int:
        try:
            expected = load_nodl(args.expected)
            actual = load_nodl(args.actual)
            differences = diff(expected, actual, node_fqn=args.node_name)
        except Exception as exc:
            print(f'ros2 nodl diff: {exc}', file=sys.stderr)
            return 2

        for difference in differences:
            print(difference)
        return 1 if differences else 0
