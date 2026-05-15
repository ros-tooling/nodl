from ros2cli.command import add_subparsers_on_demand
from ros2cli.command import CommandExtension


class NodlCommand(CommandExtension):
    """NoDL - Node Description Language tools."""

    def add_arguments(self, parser, cli_name, *, argv=None):
        self._subparser = parser
        add_subparsers_on_demand(
            parser, cli_name, '_verb', 'ros2nodl.verb', required=False, argv=argv
        )

    def main(self, *, parser, args):
        if not hasattr(args, '_verb'):
            self._subparser.print_help()
            return 0
        return getattr(args, '_verb').main(args=args)
