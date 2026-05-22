# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""The ``ros2 nodl`` command group."""

from ros2cli.command import CommandExtension, add_subparsers_on_demand


class NodlCommand(CommandExtension):
    """Inspect and validate NoDL documents."""

    def add_arguments(self, parser, cli_name):
        self._subparser = parser
        add_subparsers_on_demand(parser, cli_name, '_verb', 'ros2nodl.verb', required=False)

    def main(self, *, parser, args):
        if not hasattr(args, '_verb'):
            self._subparser.print_help()
            return 0
        return args._verb.main(args=args)
