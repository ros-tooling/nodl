from ros2cli.plugin_system import PLUGIN_SYSTEM_VERSION
from ros2cli.plugin_system import satisfies_version


class VerbExtension:
    """Extension point for 'nodl' verb extensions."""

    NAME = None
    EXTENSION_POINT_VERSION = '0.1'

    def __init__(self):
        super().__init__()
        satisfies_version(PLUGIN_SYSTEM_VERSION, '^0.1')

    def add_arguments(self, parser, cli_name):
        pass

    def main(self, *, args):
        raise NotImplementedError
