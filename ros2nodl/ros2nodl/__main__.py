# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Bare module entrypoint for ``ros2 nodl``, without calling the ROS 2 CLI

Useful for noninteractive environments with specific path needs like CMake targets, not for user facing.
"""

import argparse
import sys

from ros2nodl.verb.describe import DescribeVerb
from ros2nodl.verb.rewrite import RewriteVerb
from ros2nodl.verb.validate import ValidateVerb


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog='python -m ros2nodl', description='NoDL CLI.')
    subparsers = parser.add_subparsers(dest='command', required=True)
    verbs = {
        'describe': DescribeVerb,
        'rewrite': RewriteVerb,
        'validate': ValidateVerb,
    }
    for name, verb_cls in verbs.items():
        verb = verb_cls()
        subparser = subparsers.add_parser(name, help=verb_cls.__doc__)
        verb.add_arguments(subparser, parser.prog)
        subparser.set_defaults(main_func=verb.main)

    args = parser.parse_args(argv)
    return args.main_func(args=args)


if __name__ == '__main__':
    sys.exit(main())
