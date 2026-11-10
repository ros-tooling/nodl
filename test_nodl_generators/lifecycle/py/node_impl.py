# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Concrete lifecycle node that implements the hooks and the callbacks of the generated base.

Its action server works on a goal until the goal ends, and ``handle_deactivate`` succeeds only the goals of order 1.
"""

import threading
import time

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
        self.count_goals = []
        self.count_goals_lock = threading.Lock()

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

    def handle_deactivate(self, state):
        with self.count_goals_lock:
            goals = list(self.count_goals)
        for goal_handle in goals:
            if 1 == goal_handle.request.order:
                goal_handle.succeed()
        return TransitionCallbackReturn.SUCCESS

    def execute_lifecycle_count(self, goal_handle):
        with self.count_goals_lock:
            self.count_goals.append(goal_handle)
        deadline = time.monotonic() + 10.0
        while goal_handle.is_active and time.monotonic() < deadline:
            time.sleep(0.01)
        return Fibonacci.Result()
