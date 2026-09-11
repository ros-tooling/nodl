# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Concrete implementation of the generated action base class."""

from example_interfaces.action import Fibonacci

from test_nodl_generators.generated.actions_node import ActionsNodeBase


class ActionsNode(ActionsNodeBase):
    def execute_fibonacci(self, goal_handle):
        sequence = [0, 1]
        for _ in range(2, goal_handle.request.order):
            sequence.append(sequence[-1] + sequence[-2])
        goal_handle.succeed()
        return Fibonacci.Result(sequence=sequence[: goal_handle.request.order])
