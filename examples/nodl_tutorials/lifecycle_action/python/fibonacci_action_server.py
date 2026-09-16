#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Lifecycle Fibonacci server implemented on the generated Python base."""

import time

import rclpy
from example_interfaces.action import Fibonacci
from nodl_tutorial_lifecycle_action.generated.fibonacci_action_server_py_base import (
    FibonacciActionServerPyBase,
)
from rclpy.action import CancelResponse, GoalResponse
from rclpy.executors import MultiThreadedExecutor
from rclpy.lifecycle import TransitionCallbackReturn


class FibonacciActionServer(FibonacciActionServerPyBase):
    def __init__(self):
        super().__init__()
        self._active = False

    def on_activate(self, state):
        result = super().on_activate(state)
        self._active = result == TransitionCallbackReturn.SUCCESS
        return result

    def on_deactivate(self, state):
        self._active = False
        return super().on_deactivate(state)

    def on_fibonacci_goal(self, goal_request):
        self.get_logger().info(f'Received goal request with order {goal_request.order}')
        if not self._active or goal_request.order > 9000:
            return GoalResponse.REJECT
        return GoalResponse.ACCEPT

    def on_fibonacci_cancel(self, goal_handle):
        del goal_handle
        self.get_logger().info('Received request to cancel goal')
        return CancelResponse.ACCEPT

    def execute_fibonacci(self, goal_handle):
        feedback = Fibonacci.Feedback(sequence=[0, 1])
        for index in range(1, goal_handle.request.order):
            if goal_handle.is_cancel_requested:
                goal_handle.canceled()
                return Fibonacci.Result(sequence=feedback.sequence)
            feedback.sequence.append(feedback.sequence[index] + feedback.sequence[index - 1])
            goal_handle.publish_feedback(feedback)
            time.sleep(0.1)

        goal_handle.succeed()
        return Fibonacci.Result(sequence=feedback.sequence)


def main(args=None):
    rclpy.init(args=args)
    node = FibonacciActionServer()
    executor = MultiThreadedExecutor(num_threads=2)
    try:
        rclpy.spin(node, executor=executor)
    finally:
        executor.shutdown()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
