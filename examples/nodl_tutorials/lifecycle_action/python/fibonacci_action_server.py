#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Lifecycle Fibonacci server implemented on the generated Python base."""

import time

import rclpy
from example_interfaces.action import Fibonacci
from nodl_generated.nodl_tutorial_lifecycle_action_py.fibonacci_action_server_py_base import (
    FibonacciActionServerPyBase,
)
from rclpy.action import CancelResponse, GoalResponse
from rclpy.executors import MultiThreadedExecutor


class FibonacciActionServer(FibonacciActionServerPyBase):
    def on_fibonacci_goal(self, goal_request):
        self.get_logger().info(f'Received goal request with order {goal_request.order}')
        if not 0 <= goal_request.order <= 46:
            return GoalResponse.REJECT
        return GoalResponse.ACCEPT

    def on_fibonacci_cancel(self, goal_handle):
        del goal_handle
        self.get_logger().info('Received request to cancel goal')
        return CancelResponse.ACCEPT

    def execute_fibonacci(self, goal_handle):
        feedback = Fibonacci.Feedback(sequence=[0, 1])
        try:
            for index in range(1, goal_handle.request.order):
                if not goal_handle.is_active:
                    return Fibonacci.Result(sequence=feedback.sequence)
                if goal_handle.is_cancel_requested:
                    goal_handle.canceled()
                    return Fibonacci.Result(sequence=feedback.sequence)
                feedback.sequence.append(feedback.sequence[index] + feedback.sequence[index - 1])
                goal_handle.publish_feedback(feedback)
                time.sleep(0.1)

            if goal_handle.is_active:
                goal_handle.succeed()
        except RuntimeError:
            # Deactivation can end the goal between the active check and a feedback/finish call.
            if goal_handle.is_active:
                raise
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
