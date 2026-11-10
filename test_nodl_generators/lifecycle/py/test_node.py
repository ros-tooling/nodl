# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Runtime test for the generated entities of a lifecycle node in each state."""

import threading
import time

import pytest
import rclpy
from action_msgs.msg import GoalStatus
from example_interfaces.action import Fibonacci
from example_interfaces.srv import AddTwoInts
from node_impl import GeneratedLifecycleNode
from rclpy.action import ActionClient, ActionServer
from rclpy.executors import MultiThreadedExecutor, SingleThreadedExecutor
from rclpy.lifecycle import LifecycleNode, LifecyclePublisher, TransitionCallbackReturn
from rclpy.node import Node
from rclpy.parameter import Parameter
from std_msgs.msg import String

from nodl_runtime_py import InactiveError


@pytest.fixture
def ros_context():
    rclpy.init()
    try:
        yield
    finally:
        rclpy.shutdown()


def _spin_until(executor, predicate, timeout=10.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline and not predicate():
        executor.spin_once(timeout_sec=0.05)
    return predicate()


def test_generated_publisher_follows_lifecycle_transitions(ros_context):
    node = GeneratedLifecycleNode()
    harness = Node('lifecycle_test_harness')
    received = []
    harness.create_subscription(String, '/lifecycle_status', lambda msg: received.append(msg.data), 10)

    executor = SingleThreadedExecutor()
    executor.add_node(node)
    executor.add_node(harness)
    try:
        assert isinstance(node, LifecycleNode)
        assert isinstance(node.pub_lifecycle_status, LifecyclePublisher)
        assert _spin_until(executor, lambda: node.pub_lifecycle_status.get_subscription_count() > 0)

        node.pub_lifecycle_status.publish(String(data='inactive'))
        assert not _spin_until(executor, lambda: bool(received), timeout=0.2)

        assert node.trigger_configure() == TransitionCallbackReturn.SUCCESS
        assert node.trigger_activate() == TransitionCallbackReturn.SUCCESS
        assert node.activate_count == 1
        node.pub_lifecycle_status.publish(String(data='active'))
        assert _spin_until(executor, lambda: received == ['active'])

        assert node.trigger_deactivate() == TransitionCallbackReturn.SUCCESS
        node.pub_lifecycle_status.publish(String(data='inactive-again'))
        assert not _spin_until(executor, lambda: len(received) > 1, timeout=0.2)
    finally:
        executor.shutdown()
        node.destroy_node()
        harness.destroy_node()


def _add(request, response):
    response.sum = request.a + request.b
    return response


def _succeed(goal_handle):
    goal_handle.succeed()
    return Fibonacci.Result()


@pytest.fixture
def lifecycle_setup(ros_context):
    node = GeneratedLifecycleNode()
    harness = Node('lifecycle_gate_harness')
    executor = SingleThreadedExecutor()
    executor.add_node(node)
    executor.add_node(harness)
    command_pub = harness.create_publisher(String, '/lifecycle_command', 10)
    add_client = harness.create_client(AddTwoInts, '/lifecycle_add')
    harness.create_service(AddTwoInts, '/lifecycle_remote_add', _add)
    ActionServer(harness, Fibonacci, '/lifecycle_fibonacci', _succeed)
    try:
        yield node, executor, command_pub, add_client
    finally:
        executor.shutdown()
        node.destroy_node()
        harness.destroy_node()


def _send_command(executor, command_pub, data):
    assert _spin_until(executor, lambda: command_pub.get_subscription_count() > 0)
    command_pub.publish(String(data=data))


def _call_add(executor, add_client, a, b):
    assert _spin_until(executor, add_client.service_is_ready)
    return add_client.call_async(AddTwoInts.Request(a=a, b=b))


def test_generated_subscription_delivers_only_while_active(lifecycle_setup):
    node, executor, command_pub, _ = lifecycle_setup

    _send_command(executor, command_pub, 'unconfigured')
    assert not _spin_until(executor, lambda: bool(node.commands), timeout=0.3)

    node.trigger_configure()
    _send_command(executor, command_pub, 'inactive')
    assert not _spin_until(executor, lambda: bool(node.commands), timeout=0.3)

    node.trigger_activate()
    _send_command(executor, command_pub, 'active')
    assert _spin_until(executor, lambda: ['active'] == node.commands)

    node.trigger_deactivate()
    _send_command(executor, command_pub, 'inactive-again')
    assert not _spin_until(executor, lambda: len(node.commands) > 1, timeout=0.3)


def test_generated_service_responds_only_while_active(lifecycle_setup):
    node, executor, _, add_client = lifecycle_setup

    unconfigured = _call_add(executor, add_client, 1, 2)
    assert not _spin_until(executor, unconfigured.done, timeout=0.3)

    node.trigger_configure()
    inactive = _call_add(executor, add_client, 1, 2)
    assert not _spin_until(executor, inactive.done, timeout=0.3)

    node.trigger_activate()
    active = _call_add(executor, add_client, 3, 4)
    assert _spin_until(executor, active.done)
    assert 7 == active.result().sum

    node.trigger_deactivate()
    inactive_again = _call_add(executor, add_client, 5, 6)
    assert not _spin_until(executor, inactive_again.done, timeout=0.3)


def test_generated_clients_send_only_while_the_gate_is_open(lifecycle_setup):
    node, executor, _, _ = lifecycle_setup

    assert node.trigger_configure() == TransitionCallbackReturn.SUCCESS
    assert 2 == len(node.configure_errors)

    assert node.trigger_activate() == TransitionCallbackReturn.SUCCESS
    service_response, goal_handle = node.activate_futures
    assert _spin_until(executor, service_response.done)
    assert 3 == service_response.result().sum
    assert _spin_until(executor, goal_handle.done)
    assert goal_handle.result().accepted

    assert node.trigger_deactivate() == TransitionCallbackReturn.SUCCESS
    with pytest.raises(InactiveError):
        node.cli_lifecycle_remote_add.call_async(AddTwoInts.Request(a=1, b=2))


def test_generated_action_server_ends_goals_on_deactivate(ros_context):
    node = GeneratedLifecycleNode()
    harness = Node('lifecycle_action_harness')
    client = ActionClient(harness, Fibonacci, '/lifecycle_count')
    executor = MultiThreadedExecutor(num_threads=4)
    executor.add_node(node)
    executor.add_node(harness)
    spinner = threading.Thread(target=executor.spin)
    spinner.start()

    def wait_until(predicate):
        deadline = time.monotonic() + 10.0
        while time.monotonic() < deadline and not predicate():
            time.sleep(0.01)
        return predicate()

    def send(order):
        future = client.send_goal_async(Fibonacci.Goal(order=order))
        assert wait_until(future.done)
        return future.result()

    def status_of(goal_handle):
        future = goal_handle.get_result_async()
        assert wait_until(future.done)
        return future.result().status

    try:
        assert client.wait_for_server(10.0)
        assert not send(0).accepted

        assert node.trigger_configure() == TransitionCallbackReturn.SUCCESS
        assert node.trigger_activate() == TransitionCallbackReturn.SUCCESS
        still_active = send(0)
        succeeded_by_hook = send(1)
        assert still_active.accepted
        assert succeeded_by_hook.accepted
        assert wait_until(lambda: 2 == len(node.count_goals))

        assert node.trigger_deactivate() == TransitionCallbackReturn.SUCCESS

        assert GoalStatus.STATUS_ABORTED == status_of(still_active)
        assert GoalStatus.STATUS_SUCCEEDED == status_of(succeeded_by_hook)
        assert not send(0).accepted
    finally:
        executor.shutdown()
        spinner.join(10.0)
        node.destroy_node()
        harness.destroy_node()


def test_generated_parameters_are_refreshed_by_transitions_and_live_only_while_active(ros_context):
    node = GeneratedLifecycleNode()
    try:
        assert node.params_.gain == 1.0

        node.set_parameters([Parameter('gain', value=2.0)])
        assert node.params_.gain == 1.0
        assert node.trigger_configure() == TransitionCallbackReturn.SUCCESS
        assert node.gain_in_hook['configure'] == 2.0

        node.set_parameters([Parameter('gain', value=3.0)])
        assert node.params_.gain == 2.0
        assert node.trigger_activate() == TransitionCallbackReturn.SUCCESS
        assert node.gain_in_hook['activate'] == 3.0
        assert node.changes == []

        assert node.set_parameters([Parameter('gain', value=4.0)])[0].successful
        assert node.params_.gain == 4.0
        assert node.changes == [4.0]
        assert not node.set_parameters([Parameter('gain', value=-1.0)])[0].successful
        assert node.params_.gain == 4.0
        assert node.changes == [4.0]

        assert node.trigger_deactivate() == TransitionCallbackReturn.SUCCESS
        node.set_parameters([Parameter('gain', value=5.0)])
        assert node.params_.gain == 4.0
        assert node.changes == [4.0]

        assert node.trigger_activate() == TransitionCallbackReturn.SUCCESS
        assert node.gain_in_hook['activate'] == 5.0
        assert node.changes == [4.0]
    finally:
        node.destroy_node()
