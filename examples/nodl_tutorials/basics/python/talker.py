# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
import rclpy
from example_interfaces.msg import String

from nodl.talker_base import TalkerBase


class Talker(TalkerBase):
    def __init__(self):
        super().__init__()
        self.count = 0
        self.timer = self.create_timer(0.5, self.on_timer)

    def on_timer(self):
        message = String(data=f'Hello World: {self.count}')
        self.pub_chatter.publish(message)
        self.count += 1


def main(args=None):
    rclpy.init(args=args)
    node = Talker()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
