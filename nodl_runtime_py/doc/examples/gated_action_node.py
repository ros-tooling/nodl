# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""A hand-written (non-generated) lifecycle node whose action goals end when it deactivates."""

import sys
import time

from example_interfaces.action import Fibonacci
from rclpy.executors import MultiThreadedExecutor

from nodl_runtime_py import GatedActionServer, run_node
from nodl_runtime_py.lifecycle import LifecycleNode


class Counter(LifecycleNode):
    def __init__(self):
        super().__init__('counter')
        # The server is created by hand to keep the example self-contained, where a generated node creates its own.
        self.server = GatedActionServer(self, Fibonacci, 'count', self._execute)
        self.add_managed_entity(self.server)

    def _execute(self, goal_handle):
        feedback = Fibonacci.Feedback()
        while goal_handle.is_active:
            feedback.sequence.append(len(feedback.sequence))
            goal_handle.publish_feedback(feedback)
            time.sleep(0.1)
        # The node ended the goal by deactivating, and the client receives this result.
        return Fibonacci.Result(sequence=feedback.sequence)


def main():
    # The execute callback blocks, so the executor needs another thread to service the deactivation.
    return run_node(Counter, executor_class=MultiThreadedExecutor)


if __name__ == '__main__':
    sys.exit(main())
