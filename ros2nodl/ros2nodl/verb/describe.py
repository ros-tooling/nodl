# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""``ros2 nodl describe NODE_NAME [knobs...]`` -- observe a running node and publish its description."""

import argparse
import os
import sys
import time

from ros2nodl.verb import VerbExtension

_DEFAULT_TOPIC = '/nodl/observed_node'
_DEFAULT_TIMEOUT = 5.0


def _infer_format(path: str) -> str:
    """Return 'yaml' or 'json' inferred from *path*'s extension.

    Raises :class:`argparse.ArgumentTypeError` for any other extension so the
    caller can surface it as an argparse-level error before ROS is initialised.
    """
    _, ext = os.path.splitext(path)
    ext = ext.lower()
    if ext in ('.yaml', '.yml'):
        return 'yaml'
    if ext == '.json':
        return 'json'
    raise argparse.ArgumentTypeError(
        f'-o/--output: unrecognised extension "{ext}"; '
        'use .yaml, .yml, or .json'
    )


class DescribeVerb(VerbExtension):
    """Observe a running node and publish its description as rosgraph_msgs/Node."""

    def add_arguments(self, parser, cli_name):
        parser.add_argument(
            'node_name',
            metavar='NODE_NAME',
            help='Fully-qualified name of the target node (e.g. /my_namespace/my_node).',
        )
        parser.add_argument(
            '--timeout',
            metavar='SEC',
            type=float,
            default=_DEFAULT_TIMEOUT,
            help=(
                'Maximum time in seconds to wait for discovery, parameter services, '
                'and publish acknowledgement (default: %(default)s).'
            ),
        )
        parser.add_argument(
            '--no-params',
            action='store_true',
            default=False,
            dest='no_params',
            help=(
                'Skip remote parameter service calls. '
                'Faster and zero-contact with the target node.'
            ),
        )
        parser.add_argument(
            '--topic',
            metavar='NAME',
            default=_DEFAULT_TOPIC,
            help='Latched topic to publish the observation on (default: %(default)s).',
        )
        parser.add_argument(
            '-o', '--output',
            metavar='FILE',
            default=None,
            dest='output',
            help=(
                'Write the description to FILE instead of stdout. '
                'Format is inferred from the extension: .yaml/.yml or .json.'
            ),
        )

    def main(self, *, args):
        # Validate the output extension before touching ROS so the error is clean.
        output_format = None
        if args.output is not None:
            try:
                output_format = _infer_format(args.output)
            except argparse.ArgumentTypeError as e:
                print(str(e), file=sys.stderr)
                return 1

        return _run(
            node_name=args.node_name,
            timeout_sec=args.timeout,
            include_parameters=not args.no_params,
            topic=args.topic,
            output_path=args.output,
            output_format=output_format,
        )


def _run(
    *,
    node_name: str,
    timeout_sec: float,
    include_parameters: bool,
    topic: str,
    output_path,
    output_format,
) -> int:
    import rclpy
    from rclpy.duration import Duration

    try:
        from nodl_observe import NodeNotFoundError, latched_qos, observe_node
        from nodl_observe.serialization import to_json, to_yaml
    except ImportError as e:
        # rosgraph_msgs < 2.0.4 (e.g. older distros) has no Node message.
        print(
            f'ros2 nodl describe: observation support unavailable ({e}); '
            'rosgraph_msgs >= 2.0.4 is required.',
            file=sys.stderr,
        )
        return 1

    observer_name = f'_ros2nodl_describe_{os.getpid()}'
    # Own the rclpy lifecycle only if nobody initialised it yet.  In production
    # the CLI is the sole owner; an embedding caller (e.g. an in-process test
    # harness) that already called rclpy.init() keeps ownership.
    try:
        rclpy.init()
        owns_context = True
    except RuntimeError:
        owns_context = False
    try:
        node = rclpy.create_node(observer_name, start_parameter_services=False)
        try:
            deadline = time.monotonic() + timeout_sec
            try:
                msg = observe_node(
                    node,
                    node_name,
                    timeout_sec=timeout_sec,
                    include_parameters=include_parameters,
                )
            except NodeNotFoundError:
                print(
                    f'ros2 nodl describe: node not found: {node_name!r}',
                    file=sys.stderr,
                )
                return 1

            # Serialise for stdout / file.
            yaml_text = to_yaml(msg)

            if output_path is None:
                print(yaml_text, end='')
            else:
                if output_format == 'json':
                    text = to_json(msg)
                else:
                    text = yaml_text
                try:
                    with open(output_path, 'w') as fh:
                        fh.write(text)
                except OSError as e:
                    print(f'ros2 nodl describe: {e}', file=sys.stderr)
                    return 1

            # Latched publish: transient_local, keep_last(1), reliable.
            pub = node.create_publisher(type(msg), topic, latched_qos())
            pub.publish(msg)

            # Wait for all currently-matched subscribers to acknowledge receipt,
            # bounded by whatever budget is left on the timeout clock.
            remaining = max(0.0, deadline - time.monotonic())
            try:
                acked = pub.wait_for_all_acked(Duration(seconds=remaining))
            except NotImplementedError:
                # The RMW cannot track acknowledgements; best-effort then.
                acked = True
            if not acked:
                print(
                    'ros2 nodl describe: warning: subscribers did not all '
                    'acknowledge the published description within the timeout',
                    file=sys.stderr,
                )

        finally:
            node.destroy_node()
    finally:
        if owns_context:
            rclpy.shutdown()

    return 0
