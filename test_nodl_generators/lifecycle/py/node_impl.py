# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Concrete lifecycle node that defines the activation hook of the generated base."""

from nodl_generated.test_nodl_generators.lifecycle_node_base import LifecycleNodeBase
from rclpy.lifecycle import TransitionCallbackReturn


class GeneratedLifecycleNode(LifecycleNodeBase):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.activations = 0
        self.cmd_received = []
        self.latched_received = []
        self.state_of_latched_sample = None

    def handle_activate(self, state):
        self.activations += 1
        return TransitionCallbackReturn.SUCCESS

    def on_cmd(self, msg):
        self.cmd_received.append(msg.data)

    def on_latched(self, msg):
        self.state_of_latched_sample = self._state_machine.current_state[0]
        self.latched_received.append(msg.data)
