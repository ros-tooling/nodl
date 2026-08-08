# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""``ros2 nodl describe`` command."""

import argparse
import json
import os
import sys

from ros2nodl.verb import VerbExtension

_DEFAULT_TIMEOUT = 5.0


def _infer_format(path: str) -> str:
    extension = os.path.splitext(path)[1].lower()
    if extension in ('.yaml', '.yml'):
        return 'yaml'
    if extension == '.json':
        return 'json'
    raise argparse.ArgumentTypeError(f'-o/--output: unrecognised extension "{extension}"; use .yaml, .yml, or .json')


class DescribeVerb(VerbExtension):
    """Create a NoDL draft from a running or captured node."""

    def add_arguments(self, parser, cli_name):
        parser.add_argument('node_name', metavar='NODE_NAME', help='Fully-qualified target node name.')
        parser.add_argument(
            '--from',
            metavar='FILE',
            dest='from_file',
            help='Read a captured Node from YAML or MCAP instead of observing live.',
        )
        parser.add_argument(
            '--timeout',
            metavar='SEC',
            type=float,
            default=_DEFAULT_TIMEOUT,
            help='Live discovery timeout in seconds (default: %(default)s).',
        )
        parser.add_argument(
            '--no-params',
            action='store_true',
            dest='no_params',
            help='Omit parameters and skip live parameter service calls.',
        )
        parser.add_argument(
            '--include-ros-infra',
            action='store_true',
            help='Include framework-created endpoints and parameters.',
        )
        parser.add_argument(
            '--fail-on-warnings',
            action='store_true',
            help='Fail when any field cannot be recovered.',
        )
        parser.add_argument(
            '-o',
            '--output',
            metavar='FILE',
            help='Write YAML or JSON, inferred from the extension.',
        )

    def main(self, *, args):
        try:
            output_format = _infer_format(args.output) if args.output else 'yaml'
        except argparse.ArgumentTypeError as exc:
            print(exc, file=sys.stderr)
            return 1
        return _run(
            node_name=args.node_name,
            from_file=args.from_file,
            timeout_sec=args.timeout,
            include_parameters=not args.no_params,
            keep_hidden=args.include_ros_infra,
            fail_on_warnings=args.fail_on_warnings,
            output_path=args.output,
            output_format=output_format,
        )


def _acquire_node(*, node_name, from_file, timeout_sec, include_parameters):
    from ros2nodl.describe import _source

    if from_file:
        return _source.acquire_from_file(from_file)
    return _source.acquire_live(
        node_name,
        timeout_sec=timeout_sec,
        include_parameters=include_parameters,
    )


def _write(text: str, output_path) -> int:
    text = text if text.endswith('\n') else text + '\n'
    if output_path is None:
        print(text, end='')
        return 0
    try:
        with open(output_path, 'w') as output:
            output.write(text)
    except OSError as exc:
        print(f'ros2 nodl describe: {exc}', file=sys.stderr)
        return 1
    return 0


def _run(
    *,
    node_name,
    from_file,
    timeout_sec,
    include_parameters,
    keep_hidden,
    fail_on_warnings,
    output_path,
    output_format,
) -> int:
    from ros2nodl.describe._source import SourceError

    try:
        message = _acquire_node(
            node_name=node_name,
            from_file=from_file,
            timeout_sec=timeout_sec,
            include_parameters=include_parameters,
        )
    except SourceError as exc:
        print(f'ros2 nodl describe: {exc}', file=sys.stderr)
        return 1

    from nodl_schema.loader import dump_nodl
    from nodl_schema.validation import validate
    from ros2nodl.describe import DescribeOptions, node_to_nodl

    try:
        result = node_to_nodl(
            message,
            DescribeOptions(
                include_parameters=include_parameters,
                keep_hidden=keep_hidden,
            ),
        )
    except Exception as exc:
        print(f'ros2 nodl describe: failed to interpret node: {exc}', file=sys.stderr)
        return 1

    try:
        validate(json.loads(result.doc.json(exclude_none=True)))
    except Exception as exc:
        print(f'ros2 nodl describe: document failed validation: {exc}', file=sys.stderr)
        return 1

    for gap in result.gaps:
        print(f'ros2 nodl describe: {gap.path}: {gap.reason}', file=sys.stderr)

    write_result = _write(dump_nodl(result.doc, format=output_format), output_path)
    if write_result:
        return write_result
    return int(bool(fail_on_warnings and result.gaps))
