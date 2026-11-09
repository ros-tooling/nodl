# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""A hand-written (non-generated) node using nodl_runtime_py.lifecycle.LifecycleNode to gate a subscription, a service and clients on activation."""

import sys

from example_interfaces.action import Fibonacci
from example_interfaces.msg import Int32
from example_interfaces.srv import AddTwoInts
from rclpy.action.client import ActionClient

from nodl_runtime_py import (
    GatedActionClient,
    GatedClient,
    create_gated_service,
    gate_subscription_callback,
    run_node,
)
from nodl_runtime_py.lifecycle import LifecycleNode


class Calculator(LifecycleNode):
    def __init__(self):
        super().__init__('calculator')
        self.last_number = 0

        # The base class opens and closes this gate with the node's activation.
        gate = self.activation_gate
        self.create_subscription(Int32, 'number', gate_subscription_callback(gate, self._on_number), 10)
        create_gated_service(self, gate, AddTwoInts, 'add', self._on_add)
        self.remote_add = GatedClient(gate, self.create_client(AddTwoInts, 'remote_add'))
        self.fibonacci = GatedActionClient(gate, ActionClient(self, Fibonacci, 'fibonacci'))

    def _on_number(self, msg):
        self.last_number = msg.data

    def _on_add(self, request, response):
        response.sum = request.a + request.b
        return response


def main():
    return run_node(Calculator)


if __name__ == '__main__':
    sys.exit(main())
