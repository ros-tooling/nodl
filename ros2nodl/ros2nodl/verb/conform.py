# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""``ros2 nodl conform`` -- check a running node against a NoDL document."""

import sys
from pathlib import Path

from ros2nodl.verb import VerbExtension

_DEFAULT_TIMEOUT = 15.0


class ConformVerb(VerbExtension):
    """Check whether a running node conforms to a NoDL document."""

    def add_arguments(self, parser, cli_name):
        parser.add_argument('node_name', metavar='NODE_NAME', help='Fully-qualified target node name.')
        parser.add_argument(
            '--file',
            type=Path,
            required=True,
            metavar='FILE',
            help='NoDL document that declares the expected interface.',
        )
        parser.add_argument(
            '--timeout',
            metavar='SEC',
            type=float,
            default=_DEFAULT_TIMEOUT,
            help='Live discovery timeout in seconds (default: %(default)s).',
        )
        parser.add_argument(
            '--ignore',
            action='append',
            default=[],
            metavar='RULE',
            help='Ignore observed entities that the document does not declare, as KIND:NAME[:TYPE].'
            ' NAME and TYPE are globs, for example publisher:/topic_statistics. Repeatable.',
        )

    def main(self, *, args) -> int:
        from ros2nodl.conformance import assert_conforms, format_ignored

        try:
            report = assert_conforms(
                nodl_file=str(args.file),
                node_fqn=args.node_name,
                timeout_sec=args.timeout,
                ignore=args.ignore,
            )
        except Exception as exc:
            print(f'ros2 nodl conform: {exc}', file=sys.stderr)
            return 1
        print(f'{args.node_name}: conforms')
        if report.ignored:
            print(format_ignored(report))
        return 0
