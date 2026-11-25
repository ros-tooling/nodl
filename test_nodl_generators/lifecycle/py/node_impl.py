# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Concrete lifecycle node that defines the activation hook of the generated base."""

from nodl_generated.test_nodl_generators.lifecycle_node_base import LifecycleNodeBase
from rclpy.lifecycle import TransitionCallbackReturn
from std_srvs.srv import Trigger


class GeneratedLifecycleNode(LifecycleNodeBase):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.activations = 0
        self.cmd_received = []
        self.latched_received = []
        self.ping_in_activate = False
        self.ping_responses = 0

    def handle_activate(self, state):
        self.activations += 1
        # The client exists from construction, but its server can still be undiscovered right after startup.
        if (client := self.cli_lifecycle_ping.get()) is not None:
            self.ping_in_activate = True
            if client.wait_for_service(timeout_sec=2.0):
                client.call_async(Trigger.Request()).add_done_callback(self._on_ping_response)
        return TransitionCallbackReturn.SUCCESS

    def on_cmd(self, msg):
        self.cmd_received.append(msg.data)

    def on_latched(self, msg):
        self.latched_received.append(msg.data)

    def on_lifecycle_add(self, request, response):
        response.sum = request.a + request.b
        return response

    def _on_ping_response(self, future):
        self.ping_responses += 1
