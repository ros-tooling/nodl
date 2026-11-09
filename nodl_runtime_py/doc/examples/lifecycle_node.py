# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""A hand-written (non-generated) node using nodl_runtime_py.lifecycle.LifecycleNode to illustrate the lifecycle hooks."""

import sys

from rclpy.lifecycle import TransitionCallbackReturn
from std_msgs.msg import String

from nodl_runtime_py import run_node
from nodl_runtime_py.lifecycle import LifecycleNode


class Talker(LifecycleNode):
    def __init__(self):
        super().__init__('talker')
        # The base class activates this publisher with the node, so handle_activate needs no code for it.
        self._publisher = self.create_lifecycle_publisher(String, 'chatter', 10)
        self.create_timer(0.1, self._talk)

    def handle_configure(self, state):
        self.get_logger().info('Configured')
        return TransitionCallbackReturn.SUCCESS

    def handle_activate(self, state):
        self.get_logger().info('Activated')
        return TransitionCallbackReturn.SUCCESS

    def handle_shutdown(self, state):
        self.get_logger().info('Shut down')
        return TransitionCallbackReturn.SUCCESS

    def _talk(self):
        self._publisher.publish(String(data='Hello'))
        if self._publisher.is_activated:
            self.get_logger().info('Publishing')


def main():
    return run_node(Talker)


if __name__ == '__main__':
    sys.exit(main())
