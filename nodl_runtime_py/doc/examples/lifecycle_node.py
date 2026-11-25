# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""A lifecycle node that greets and listens for names only while it is active, run as an executable."""

import sys

from rclpy.lifecycle import LifecycleState, TransitionCallbackReturn
from std_msgs.msg import String
from std_srvs.srv import Trigger

from nodl_runtime_py import Gated, Managed, run_node
from nodl_runtime_py.lifecycle import LifecycleNode


class Greeter(LifecycleNode):
    """Greet from a timer that runs between handle_activate and handle_deactivate, and greet each name received while active.

    It also calls a service from handle_activate and from the timer, through a client that is handed out only while the node is active.
    """

    def __init__(self):
        super().__init__('greeter')
        # A lifecycle publisher drops messages while the node is not active.
        self.pub_greeting = self.create_lifecycle_publisher(String, 'greeting', 10)
        # A subscription exists only while the node is active.
        self._sub_name = Managed(
            self,
            lambda: self.create_subscription(String, 'name', self._on_name, 10),
            self.destroy_subscription,
        )
        # A client exists for the lifetime of the node, and is handed out only while the node is active.
        self._cli_notify = Gated(self, self.create_client(Trigger, 'notify'))
        self._timer = None

    def handle_activate(self, state: LifecycleState) -> TransitionCallbackReturn:
        self._greet('everyone')
        self._notify()
        # Create timers last, so that a failing hook leaves none of them firing.
        self._timer = self.create_timer(1.0, self._on_timer)
        return TransitionCallbackReturn.SUCCESS

    # This hook also runs first on shutdown and error from the active state.
    def handle_deactivate(self, state: LifecycleState) -> TransitionCallbackReturn:
        if self._timer is not None:
            self.destroy_timer(self._timer)
            self._timer = None
        self.get_logger().info('goodbye')
        return TransitionCallbackReturn.SUCCESS

    def _on_name(self, msg: String) -> None:
        self._greet(msg.data)

    def _on_timer(self) -> None:
        self._greet('again')
        self._notify()

    def _notify(self) -> None:
        # The client is None while the node is not active, so check it at each use.
        if (client := self._cli_notify.get()) is not None:
            client.call_async(Trigger.Request())

    def _greet(self, name: str) -> None:
        self.pub_greeting.publish(String(data=f'hello {name}'))
        self.get_logger().info(f'greeted {name}')


def main():
    return run_node(Greeter)


if __name__ == '__main__':
    sys.exit(main())
