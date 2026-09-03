# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Concrete implementation of the generated interface base class."""

from example_interfaces.action import Fibonacci
from std_msgs.msg import String

from test_nodl_generator_py._generated.interfaces_node import InterfacesNodeBase


class InterfacesNode(InterfacesNodeBase):
    def on_echo_in(self, msg):
        self.pub_echo_out.publish(String(data=f'{self.params_.greeting}: {msg.data}'))

    def on_add(self, request, response):
        response.sum = request.a + request.b
        return response

    def execute_fibonacci(self, goal_handle):
        sequence = [0, 1]
        for _ in range(2, goal_handle.request.order):
            sequence.append(sequence[-1] + sequence[-2])
        goal_handle.succeed()
        return Fibonacci.Result(sequence=sequence[: goal_handle.request.order])
