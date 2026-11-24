# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Concrete implementation of the generated interface base class."""

from example_interfaces.action import Fibonacci
from nodl_generated.test_nodl_generators.kitchen_sink_node_base import KitchenSinkNodeBase
from std_msgs.msg import String


class KitchenSinkNode(KitchenSinkNodeBase):
    def on_input(self, msg):
        self.pub_output.publish(String(data=f'{self.params_.greeting}: {msg.data}'))

    def on_sum(self, request, response):
        response.sum = request.a + request.b
        return response

    def execute_sequence(self, goal_handle):
        sequence = [0, 1]
        for _ in range(2, goal_handle.request.order):
            sequence.append(sequence[-1] + sequence[-2])
        goal_handle.succeed()
        return Fibonacci.Result(sequence=sequence[: goal_handle.request.order])
