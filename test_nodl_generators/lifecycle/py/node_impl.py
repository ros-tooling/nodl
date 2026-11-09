# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Concrete lifecycle node that implements the activate hook and the callbacks of the generated base."""

from example_interfaces.action import Fibonacci
from example_interfaces.srv import AddTwoInts
from nodl_generated.test_nodl_generators.lifecycle_node_base import LifecycleNodeBase
from rclpy.lifecycle import TransitionCallbackReturn

from nodl_runtime_py import InactiveError


class GeneratedLifecycleNode(LifecycleNodeBase):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.activate_count = 0
        self.commands = []
        self.configure_errors = []
        self.activate_futures = []

    def handle_configure(self, state):
        for send in (
            lambda: self.cli_lifecycle_remote_add.call_async(AddTwoInts.Request(a=1, b=2)),
            lambda: self.action_cli_lifecycle_fibonacci.send_goal_async(Fibonacci.Goal(order=1)),
        ):
            try:
                send()
            except InactiveError as error:
                self.configure_errors.append(error)
        return TransitionCallbackReturn.SUCCESS

    def handle_activate(self, state):
        self.activate_count += 1
        self.activate_futures = [
            self.cli_lifecycle_remote_add.call_async(AddTwoInts.Request(a=1, b=2)),
            self.action_cli_lifecycle_fibonacci.send_goal_async(Fibonacci.Goal(order=1)),
        ]
        return TransitionCallbackReturn.SUCCESS

    def on_lifecycle_command(self, msg):
        self.commands.append(msg.data)

    def on_lifecycle_add(self, request, response):
        response.sum = request.a + request.b
        return response
