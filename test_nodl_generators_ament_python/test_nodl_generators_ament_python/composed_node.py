# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Subclass of the generated base class whose document includes another by source-tree path."""

from std_msgs.msg import String

from test_nodl_generators_ament_python.generated.composed_node_base import ComposedNodeBase


class ComposedNode(ComposedNodeBase):
    def on_composed_in(self, msg):
        self.pub_status.publish(String(data=msg.data))
