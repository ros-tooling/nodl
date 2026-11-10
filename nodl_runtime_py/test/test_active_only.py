# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0

import asyncio
import inspect
import sys
import time
from pathlib import Path

import pytest
import rclpy
from example_interfaces.action import Fibonacci
from example_interfaces.msg import Int32
from example_interfaces.srv import AddTwoInts
from rclpy.action import ActionClient, ActionServer
from rclpy.client import Client
from rclpy.executors import SingleThreadedExecutor
from rclpy.lifecycle import SimpleManagedEntity
from rclpy.node import Node

from nodl_runtime_py import InactiveError, active_only_subscription_callback, create_active_only_service

sys.path.insert(0, str(Path(__file__).parent.parent / 'doc' / 'examples'))

from active_only_node import Calculator  # noqa: E402

# How long to spin when waiting for something that must not happen.
QUIET_S = 0.5
TIMEOUT_S = 10


class Peer(Node):
    """The other end of the calculator's entities, never active-only."""

    def __init__(self):
        super().__init__('peer')
        self.number_pub = self.create_publisher(Int32, 'number', 10)
        self.add_client = self.create_client(AddTwoInts, 'add')
        self.remote_add_service = self.create_service(AddTwoInts, 'remote_add', self._on_add)
        self.fibonacci_server = ActionServer(self, Fibonacci, 'fibonacci', self._execute)

    @staticmethod
    def _on_add(request, response):
        response.sum = request.a + request.b
        return response

    @staticmethod
    def _execute(goal_handle):
        goal_handle.succeed()
        return Fibonacci.Result()


class Spinner:
    """One executor with the calculator and its peer."""

    def __init__(self):
        self.calculator = Calculator()
        self.peer = Peer()
        self.executor = SingleThreadedExecutor()
        self.executor.add_node(self.calculator)
        self.executor.add_node(self.peer)

    def spin_for(self, seconds):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            self.executor.spin_once(timeout_sec=0.05)

    def spin_until(self, condition):
        deadline = time.monotonic() + TIMEOUT_S
        while not condition():
            assert time.monotonic() < deadline, 'timed out'
            self.executor.spin_once(timeout_sec=0.05)

    def activate(self):
        self.calculator.trigger_configure()
        self.calculator.trigger_activate()

    def deactivate(self):
        self.calculator.trigger_deactivate()


@pytest.fixture
def spinner():
    rclpy.init()
    spinner = Spinner()
    yield spinner
    spinner.executor.shutdown()
    spinner.calculator.destroy_node()
    spinner.peer.destroy_node()
    rclpy.shutdown()


def publish_number(spinner, value):
    # Give discovery time, so that the message is not lost.
    spinner.spin_until(lambda: spinner.peer.number_pub.get_subscription_count() > 0)
    spinner.peer.number_pub.publish(Int32(data=value))


def test_subscription_callback_not_called_while_closed(spinner):
    spinner.calculator.trigger_configure()
    publish_number(spinner, 5)
    spinner.spin_for(QUIET_S)
    assert 0 == spinner.calculator.last_number


def test_subscription_callback_called_while_open(spinner):
    spinner.activate()
    publish_number(spinner, 5)
    spinner.spin_until(lambda: 5 == spinner.calculator.last_number)


def test_subscription_callback_stops_after_deactivate(spinner):
    spinner.activate()
    spinner.deactivate()
    publish_number(spinner, 5)
    spinner.spin_for(QUIET_S)
    assert 0 == spinner.calculator.last_number


def test_service_request_gets_no_response_while_closed(spinner):
    spinner.calculator.trigger_configure()
    spinner.peer.add_client.wait_for_service(TIMEOUT_S)
    future = spinner.peer.add_client.call_async(AddTwoInts.Request(a=1, b=2))
    # An exception raised into the executor by a dropped request propagates from spin_once.
    spinner.spin_for(QUIET_S)
    assert not future.done()


def test_service_response_sent_while_open(spinner):
    spinner.activate()
    spinner.peer.add_client.wait_for_service(TIMEOUT_S)
    future = spinner.peer.add_client.call_async(AddTwoInts.Request(a=1, b=2))
    spinner.spin_until(future.done)
    assert 3 == future.result().sum


def test_service_responds_again_after_reactivation(spinner):
    spinner.activate()
    spinner.deactivate()
    spinner.peer.add_client.wait_for_service(TIMEOUT_S)
    dropped = spinner.peer.add_client.call_async(AddTwoInts.Request(a=1, b=2))
    spinner.spin_for(QUIET_S)
    assert not dropped.done()
    spinner.calculator.trigger_activate()
    answered = spinner.peer.add_client.call_async(AddTwoInts.Request(a=3, b=4))
    spinner.spin_until(answered.done)
    assert 7 == answered.result().sum


def test_service_client_send_raises_while_closed(spinner):
    spinner.calculator.trigger_configure()
    with pytest.raises(InactiveError, match='remote_add'):
        spinner.calculator.remote_add.call_async(AddTwoInts.Request(a=1, b=2))


def test_service_client_send_succeeds_while_open(spinner):
    spinner.activate()
    spinner.spin_until(spinner.calculator.remote_add.service_is_ready)
    future = spinner.calculator.remote_add.call_async(AddTwoInts.Request(a=1, b=2))
    spinner.spin_until(future.done)
    assert 3 == future.result().sum


def test_service_client_response_arrives_after_deactivate(spinner):
    spinner.activate()
    spinner.spin_until(spinner.calculator.remote_add.service_is_ready)
    future = spinner.calculator.remote_add.call_async(AddTwoInts.Request(a=1, b=2))
    spinner.deactivate()
    spinner.spin_until(future.done)
    assert 3 == future.result().sum


def test_clients_expose_the_wrapped_client(spinner):
    assert isinstance(spinner.calculator.remote_add.client, Client)
    assert isinstance(spinner.calculator.fibonacci.client, ActionClient)


def test_waiting_for_service_is_not_active_only(spinner):
    spinner.calculator.trigger_configure()
    spinner.spin_until(spinner.calculator.remote_add.service_is_ready)
    assert spinner.calculator.remote_add.wait_for_service(0.0)


def test_action_client_send_raises_while_closed(spinner):
    spinner.calculator.trigger_configure()
    with pytest.raises(InactiveError):
        spinner.calculator.fibonacci.send_goal_async(Fibonacci.Goal(order=1))


def test_action_client_send_succeeds_while_open(spinner):
    spinner.activate()
    spinner.spin_until(spinner.calculator.fibonacci.server_is_ready)
    future = spinner.calculator.fibonacci.send_goal_async(Fibonacci.Goal(order=1))
    spinner.spin_until(future.done)
    assert future.result().accepted


def test_waiting_for_action_server_is_not_active_only(spinner):
    spinner.calculator.trigger_configure()
    spinner.spin_until(spinner.calculator.fibonacci.server_is_ready)
    assert spinner.calculator.fibonacci.wait_for_server(0.0)


def test_subscription_wrapper_needs_only_the_gate():
    gate = SimpleManagedEntity()
    calls = []
    wrapped = active_only_subscription_callback(gate, calls.append)
    wrapped(1)
    gate.on_activate(None)
    wrapped(2)
    assert [2] == calls


def test_async_subscription_callback_active_only():
    gate = SimpleManagedEntity()
    calls = []

    async def callback(msg):
        calls.append(msg)

    wrapped = active_only_subscription_callback(gate, callback)
    assert inspect.iscoroutinefunction(wrapped)
    asyncio.run(wrapped(1))
    gate.on_activate(None)
    asyncio.run(wrapped(2))
    assert [2] == calls


@pytest.fixture
def async_service(spinner):
    async def on_add(request, response):
        response.sum = request.a + request.b
        return response

    gate = SimpleManagedEntity()
    create_active_only_service(spinner.calculator, gate, AddTwoInts, 'async_add', on_add)
    client = spinner.peer.create_client(AddTwoInts, 'async_add')
    spinner.spin_until(client.service_is_ready)
    return gate, client


def test_async_service_request_gets_no_response_while_closed(spinner, async_service):
    _, client = async_service
    future = client.call_async(AddTwoInts.Request(a=1, b=2))
    # A dropped request that reached the real send_response would raise TypeError from spin_once.
    spinner.spin_for(QUIET_S)
    assert not future.done()


def test_async_service_response_sent_while_open(spinner, async_service):
    gate, client = async_service
    gate.on_activate(None)
    future = client.call_async(AddTwoInts.Request(a=1, b=2))
    spinner.spin_until(future.done)
    assert 3 == future.result().sum


def test_async_service_responds_again_after_reactivation(spinner, async_service):
    gate, client = async_service
    gate.on_activate(None)
    gate.on_deactivate(None)
    dropped = client.call_async(AddTwoInts.Request(a=1, b=2))
    spinner.spin_for(QUIET_S)
    assert not dropped.done()
    gate.on_activate(None)
    answered = client.call_async(AddTwoInts.Request(a=3, b=4))
    spinner.spin_until(answered.done)
    assert 7 == answered.result().sum


def test_async_subscription_callback_stops_after_deactivate():
    gate = SimpleManagedEntity()
    calls = []

    async def callback(msg):
        calls.append(msg)

    wrapped = active_only_subscription_callback(gate, callback)
    gate.on_activate(None)
    asyncio.run(wrapped(1))
    gate.on_deactivate(None)
    asyncio.run(wrapped(2))
    assert [1] == calls
