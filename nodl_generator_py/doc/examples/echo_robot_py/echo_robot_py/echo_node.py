# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
import sys

from nodl_generated.echo_robot_py.echo_node_base import EchoNodeBase
from std_msgs.msg import String

from nodl_runtime_py import run_node


class EchoNode(EchoNodeBase):
    def on_echo_in(self, msg):
        params = self.params_
        self.pub_echo_out.publish(String(data=f'{params.greeting}: {msg.data}'))

    def on_parameters_changed(self, params):
        self.get_logger().info(f'greeting is now {params.greeting}')


def main():
    return run_node(EchoNode)


if __name__ == '__main__':
    sys.exit(main())
