import sys

from ros2nodl.verb import VerbExtension


class DescribeVerb(VerbExtension):
    """Introspect a running ROS 2 node and output its NoDL description."""

    def add_arguments(self, parser, cli_name):
        parser.add_argument(
            'node_name',
            help='Fully qualified node name to describe (e.g. /my_namespace/my_node).',
        )
        parser.add_argument(
            '--format',
            choices=['yaml', 'json'],
            default='yaml',
            help='Output format (default: yaml).',
        )
        parser.add_argument(
            '--assume-current-as-default',
            action='store_true',
            default=False,
            help='Treat current parameter values as default_value in the output.',
        )
        parser.add_argument(
            '--discovery-timeout',
            metavar='SEC',
            type=float,
            default=2.0,
            help='Seconds to wait for graph discovery before introspecting (default: 2.0).',
        )

    def main(self, *, args):
        from nodl.conversion import to_nodl
        from nodl.describe import describe
        from nodl.schema import dump_nodl

        try:
            node_msg = describe(
                args.node_name,
                discovery_timeout_sec=args.discovery_timeout,
            )
        except RuntimeError as e:
            print(f'Error: {e}', file=sys.stderr)
            return 1

        data = to_nodl(node_msg, assume_current_as_default=args.assume_current_as_default)
        print(dump_nodl(data, format=args.format), end='')
        return 0
