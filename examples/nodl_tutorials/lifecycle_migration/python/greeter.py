#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
import rclpy
from nodl_generated.nodl_tutorial_lifecycle_migration.greeter_py_base import GreeterPyBase
from rclpy.lifecycle import TransitionCallbackReturn
from std_msgs.msg import String
from std_srvs.srv import Trigger


class Greeter(GreeterPyBase):
    def __init__(self):
        super().__init__()
        self.timer = None

    def on_name(self, msg):
        self.greet(msg.data)

    # The client is not handed out while the node is inactive, so this sends nothing.
    def handle_configure(self, state):
        self.notify()
        return TransitionCallbackReturn.SUCCESS

    def handle_activate(self, state):
        self.greet('everyone')
        self.timer = self.create_timer(0.5, self.on_timer)
        return TransitionCallbackReturn.SUCCESS

    def handle_deactivate(self, state):
        self.destroy_timer(self.timer)
        self.timer = None
        self.pub_greeting.publish(String(data='goodbye'))
        return TransitionCallbackReturn.SUCCESS

    def on_timer(self):
        self.greet('again')
        self.notify()

    def notify(self):
        if (client := self.cli_notify.get()) is not None:
            client.call_async(Trigger.Request())

    def greet(self, name):
        self.pub_greeting.publish(String(data=f'hello {name}'))


def main(args=None):
    rclpy.init(args=args)
    node = Greeter()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
