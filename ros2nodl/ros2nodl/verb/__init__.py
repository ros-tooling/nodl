# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Extension point base class for ``ros2 nodl`` sub-verbs."""

from ros2cli.plugin_system import PLUGIN_SYSTEM_VERSION, satisfies_version


class VerbExtension:
    """The extension point for ``ros2 nodl`` verbs."""

    NAME = None
    EXTENSION_POINT_VERSION = '0.1'

    def __init__(self):
        super().__init__()
        satisfies_version(PLUGIN_SYSTEM_VERSION, '^0.1')

    def add_arguments(self, parser, cli_name):
        pass

    def main(self, *, args):
        raise NotImplementedError()
