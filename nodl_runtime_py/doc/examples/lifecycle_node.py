# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""A lifecycle node that greets only while it is active, run as an executable."""

import sys

from rclpy.lifecycle import LifecycleState, TransitionCallbackReturn
from std_msgs.msg import String

from nodl_runtime_py import run_node
from nodl_runtime_py.lifecycle import LifecycleNode


class Greeter(LifecycleNode):
    """Publish a greeting from a timer that runs between handle_activate and handle_deactivate."""

    def __init__(self):
        super().__init__('greeter')
        # A lifecycle publisher drops messages while the node is not active.
        self.pub_greeting = self.create_lifecycle_publisher(String, 'greeting', 10)
        self._timer = None

    def handle_activate(self, state: LifecycleState) -> TransitionCallbackReturn:
        self._greet('everyone')
        # Create timers last, so that a failing hook leaves none of them firing.
        self._timer = self.create_timer(1.0, lambda: self._greet('again'))
        return TransitionCallbackReturn.SUCCESS

    # This hook also runs first on shutdown and error from the active state.
    def handle_deactivate(self, state: LifecycleState) -> TransitionCallbackReturn:
        if self._timer is not None:
            self.destroy_timer(self._timer)
            self._timer = None
        self.get_logger().info('goodbye')
        return TransitionCallbackReturn.SUCCESS

    def _greet(self, name: str) -> None:
        self.pub_greeting.publish(String(data=f'hello {name}'))
        self.get_logger().info(f'greeted {name}')


def main():
    return run_node(Greeter)


if __name__ == '__main__':
    sys.exit(main())
