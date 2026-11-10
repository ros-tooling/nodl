# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Concrete lifecycle node that implements the activate hook of the generated base."""

from nodl_generated.test_nodl_generators.lifecycle_node_base import LifecycleNodeBase
from rclpy.lifecycle import TransitionCallbackReturn


class GeneratedLifecycleNode(LifecycleNodeBase):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.activate_count = 0

    def handle_activate(self, state):
        self.activate_count += 1
        return TransitionCallbackReturn.SUCCESS
