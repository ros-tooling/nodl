# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Concrete implementation of the generated pub/sub base class."""

from nodl_generated.test_nodl_generators.pubsub_node_base import PubsubNodeBase
from std_msgs.msg import String


class PubsubNode(PubsubNodeBase):
    def on_echo_in(self, msg):
        self.pub_echo_out.publish(String(data=f'echo: {msg.data}'))
