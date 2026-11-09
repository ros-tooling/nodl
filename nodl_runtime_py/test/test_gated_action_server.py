# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0

import sys
import threading
import time
from pathlib import Path

import pytest
import rclpy
from action_msgs.msg import GoalStatus
from example_interfaces.action import Fibonacci
from rclpy.action import ActionClient, CancelResponse, GoalResponse
from rclpy.executors import MultiThreadedExecutor
from rclpy.lifecycle import LifecycleNode
from rclpy.node import Node

from nodl_runtime_py import GatedActionServer

sys.path.insert(0, str(Path(__file__).parent.parent / 'doc' / 'examples'))

from gated_action_node import Counter  # noqa: E402

TIMEOUT_S = 10

# Orders that select what the execute callback does.
WORK = 0
SUCCEED = 1


def wait_until(predicate, timeout_s=TIMEOUT_S):
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return predicate()


class Fixture:
    """A gated action server on a plain lifecycle node, and a client on a peer node, spun by one executor."""

    def __init__(self):
        self.node = LifecycleNode('gated_action_node')
        self.peer = Node('gated_action_peer')
        self.lock = threading.Lock()
        self.goals = []
        self.author_goals = 0
        self.deactivate_in_goal_callback = False
        self.server = GatedActionServer(
            self.node,
            Fibonacci,
            'fibonacci',
            self.execute,
            goal_callback=self.on_goal,
            cancel_callback=lambda goal_handle: CancelResponse.ACCEPT,
        )
        self.node.add_managed_entity(self.server)
        self.client = ActionClient(self.peer, Fibonacci, 'fibonacci')
        self.executor = MultiThreadedExecutor(num_threads=4)
        self.executor.add_node(self.node)
        self.executor.add_node(self.peer)
        self.spinner = threading.Thread(target=self.executor.spin)
        self.spinner.start()
        assert self.client.wait_for_server(TIMEOUT_S)

    def on_goal(self, goal_request):
        if self.deactivate_in_goal_callback:
            self.node.trigger_deactivate()
        return GoalResponse.ACCEPT

    def execute(self, goal_handle):
        """Work until the goal ends, or succeed at once."""
        with self.lock:
            self.author_goals += 1
            self.goals.append(goal_handle)
        if SUCCEED == goal_handle.request.order:
            goal_handle.succeed()
        else:
            wait_until(lambda: not goal_handle.is_active)
        return Fibonacci.Result()

    def activate(self):
        self.node.trigger_configure()
        self.node.trigger_activate()

    def send(self, order=WORK):
        """Send a goal and return its client handle."""
        future = self.client.send_goal_async(Fibonacci.Goal(order=order))
        assert wait_until(future.done)
        return future.result()

    def send_and_start(self, order=WORK):
        """Send a goal and return its client handle once the author's execute callback runs on it."""
        count = len(self.goals)
        handle = self.send(order)
        assert handle.accepted
        assert wait_until(lambda: len(self.goals) > count)
        return handle

    def status_of(self, client_handle):
        future = client_handle.get_result_async()
        assert wait_until(future.done)
        return future.result().status

    def shutdown(self):
        self.executor.shutdown()
        self.spinner.join(TIMEOUT_S)
        self.node.destroy_node()
        self.peer.destroy_node()


@pytest.fixture
def fixture():
    rclpy.init()
    fixture = Fixture()
    yield fixture
    fixture.shutdown()
    rclpy.shutdown()


def test_goal_is_rejected_while_inactive_and_accepted_while_active(fixture):
    assert not fixture.send().accepted
    assert 0 == fixture.author_goals

    fixture.activate()
    assert fixture.send_and_start().accepted


def test_executing_goal_is_aborted_on_deactivate(fixture):
    fixture.activate()
    handle = fixture.send_and_start()

    fixture.node.trigger_deactivate()

    assert GoalStatus.STATUS_ABORTED == fixture.status_of(handle)


def test_canceling_goal_is_canceled_on_deactivate(fixture):
    fixture.activate()
    handle = fixture.send_and_start()
    handle.cancel_goal_async()
    assert wait_until(lambda: fixture.goals[0].is_cancel_requested)

    fixture.node.trigger_deactivate()

    assert GoalStatus.STATUS_CANCELED == fixture.status_of(handle)


def test_goal_that_succeeded_before_deactivation_stays_succeeded(fixture):
    fixture.activate()
    handle = fixture.send_and_start(SUCCEED)
    assert GoalStatus.STATUS_SUCCEEDED == fixture.status_of(handle)

    fixture.node.trigger_deactivate()

    assert GoalStatus.STATUS_SUCCEEDED == fixture.status_of(handle)


def test_concurrent_finish_does_not_fail_the_deactivation(fixture):
    for _ in range(10):
        fixture.activate()
        handle = fixture.send_and_start()
        go = threading.Event()

        def finish(goal_handle=fixture.goals[-1]):
            go.wait()
            try:
                goal_handle.succeed()
            except RuntimeError:
                pass  # The deactivation ended the goal first.

        finisher = threading.Thread(target=finish)
        finisher.start()
        go.set()

        fixture.node.trigger_deactivate()

        finisher.join(TIMEOUT_S)
        assert fixture.status_of(handle) in (GoalStatus.STATUS_SUCCEEDED, GoalStatus.STATUS_ABORTED)
        fixture.node.trigger_cleanup()


def test_goal_accepted_after_deactivation_started_ends_without_reaching_the_author(fixture):
    fixture.activate()
    # The goal callback runs on an executor thread, so the deactivation finishes before the accepted callback.
    fixture.deactivate_in_goal_callback = True

    handle = fixture.send()

    assert handle.accepted
    assert GoalStatus.STATUS_ABORTED == fixture.status_of(handle)
    assert 0 == fixture.author_goals


def test_goals_are_accepted_again_after_reactivation(fixture):
    fixture.activate()
    fixture.node.trigger_deactivate()
    assert not fixture.send().accepted

    fixture.node.trigger_activate()
    assert fixture.send_and_start().accepted


def test_example_node_ends_its_goal_on_deactivate(fixture):
    counter = Counter()
    fixture.executor.add_node(counter)
    client = ActionClient(fixture.peer, Fibonacci, 'count')
    try:
        assert client.wait_for_server(TIMEOUT_S)
        counter.trigger_configure()
        counter.trigger_activate()
        future = client.send_goal_async(Fibonacci.Goal(order=1))
        assert wait_until(future.done)
        handle = future.result()
        assert handle.accepted

        counter.trigger_deactivate()

        assert GoalStatus.STATUS_ABORTED == fixture.status_of(handle)
    finally:
        client.destroy()
        counter.destroy_node()
