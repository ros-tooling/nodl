#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
import rclpy
from rclpy.lifecycle import LifecycleNode, TransitionCallbackReturn
from std_msgs.msg import String
from std_srvs.srv import Trigger


class Greeter(LifecycleNode):
    def __init__(self):
        super().__init__('greeter_py')
        self.pub_greeting = self.create_lifecycle_publisher(String, 'greeting', 10)
        self.cli_notify = self.create_client(Trigger, 'notify')
        self.sub_name = None
        self.timer = None

    def on_configure(self, state):
        self.sub_name = self.create_subscription(String, 'name', self.on_name, 10)
        return TransitionCallbackReturn.SUCCESS

    def on_activate(self, state):
        super().on_activate(state)
        self.greet('everyone')
        self.timer = self.create_timer(0.5, self.on_timer)
        return TransitionCallbackReturn.SUCCESS

    def on_deactivate(self, state):
        self.destroy_timer(self.timer)
        self.timer = None
        self.pub_greeting.publish(String(data='goodbye'))
        return super().on_deactivate(state)

    def on_cleanup(self, state):
        self.destroy_subscription(self.sub_name)
        self.sub_name = None
        return TransitionCallbackReturn.SUCCESS

    def on_name(self, msg):
        self.greet(msg.data)

    def on_timer(self):
        self.greet('again')
        self.cli_notify.call_async(Trigger.Request())

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
