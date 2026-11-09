# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""A hand-written (non-generated) node using nodl_runtime_py.lifecycle.LifecycleNode to gate a subscription and a service on activation."""

import sys

from example_interfaces.msg import Int32
from example_interfaces.srv import AddTwoInts

from nodl_runtime_py import active_only_subscription_callback, create_active_only_service, run_node
from nodl_runtime_py.lifecycle import LifecycleNode


class Calculator(LifecycleNode):
    def __init__(self):
        super().__init__('calculator')
        self.last_number = 0

        # The base class opens and closes this gate with the node's activation.
        gate = self.activation_gate
        self.create_subscription(Int32, 'number', active_only_subscription_callback(gate, self._on_number), 10)
        create_active_only_service(self, gate, AddTwoInts, 'add', self._on_add)

    def _on_number(self, msg):
        self.last_number = msg.data

    def _on_add(self, request, response):
        response.sum = request.a + request.b
        return response


def main():
    return run_node(Calculator)


if __name__ == '__main__':
    sys.exit(main())
