# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""A node that logs a greeting, run as an executable."""

import sys

from rclpy.node import Node

from nodl_runtime_py import run_node


class Greeter(Node):
    def __init__(self):
        super().__init__('greeter')
        self.declare_parameter('greeting', 'Hello')
        self.create_timer(0.1, self._greet)

    def _greet(self):
        self.get_logger().info(f'{self.get_parameter("greeting").value}, world')


if __name__ == '__main__':
    sys.exit(run_node(Greeter))
