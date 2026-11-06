# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
import sys

from std_msgs.msg import String

from echo_robot_py.generated.echo_node_base import EchoNodeBase
from nodl_runtime_py import run_node


class EchoNode(EchoNodeBase):
    def on_echo_in(self, msg):
        self.pub_echo_out.publish(String(data=f'{self.params_.greeting}: {msg.data}'))


def main():
    return run_node(EchoNode)


if __name__ == '__main__':
    sys.exit(main())
