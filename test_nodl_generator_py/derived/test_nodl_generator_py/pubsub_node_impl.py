# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Concrete implementation of the generated pub/sub base class."""

from std_msgs.msg import String

from test_nodl_generator_py._generated.pubsub_node import PubsubNodeBase


class PubsubNode(PubsubNodeBase):
    def on_echo_in(self, msg):
        self.pub_echo_out.publish(String(data=f'echo: {msg.data}'))
