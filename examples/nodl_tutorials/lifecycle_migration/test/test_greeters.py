# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Run each handwritten greeter and its migrated form through the same transitions, as the migration guide describes."""

import os
import subprocess
import threading
import time
from pathlib import Path

import pytest
import rclpy
from ament_index_python.packages import get_package_prefix
from lifecycle_msgs.msg import State, Transition
from lifecycle_msgs.srv import ChangeState, GetState
from rclpy.executors import SingleThreadedExecutor
from std_msgs.msg import String
from std_srvs.srv import Trigger

PACKAGE = 'nodl_tutorial_lifecycle_migration'

# Each case is an executable, the name of its node, and whether its subscription exists while the node is inactive.
GREETERS = [
    pytest.param(('handwritten_greeter_cpp', 'greeter', True), id='handwritten-cpp'),
    pytest.param(('greeter_cpp', 'greeter', False), id='migrated-cpp'),
    pytest.param(('handwritten_greeter_py', 'greeter_py', True), id='handwritten-py'),
    pytest.param(('greeter_py', 'greeter_py', False), id='migrated-py'),
]


class Harness:
    """A peer of the greeter that spins in the background, publishes names and records what it receives."""

    def __init__(self, node_name):
        self.node_name = node_name
        self.node = rclpy.create_node('harness')
        self.greetings = []
        self.notifications = []
        self.node.create_subscription(String, 'greeting', lambda msg: self.greetings.append(msg.data), 10)
        self.node.create_service(Trigger, 'notify', self._on_notify)
        self.pub_name = self.node.create_publisher(String, 'name', 10)
        self._get_state = self.node.create_client(GetState, f'{node_name}/get_state')
        self._change_state = self.node.create_client(ChangeState, f'{node_name}/change_state')
        self._executor = SingleThreadedExecutor()
        self._executor.add_node(self.node)
        self._thread = threading.Thread(target=self._executor.spin)
        self._thread.start()

    def close(self):
        self._executor.shutdown()
        self._thread.join()
        self.node.destroy_node()

    def _on_notify(self, request, response):
        self.notifications.append(request)
        response.success = True
        return response

    def state(self):
        assert self._get_state.wait_for_service(timeout_sec=15.0)
        future = self._get_state.call_async(GetState.Request())
        assert wait_until(future.done)
        return future.result().current_state.id

    def transition(self, transition_id, expected_state):
        assert self._change_state.wait_for_service(timeout_sec=15.0)
        request = ChangeState.Request()
        request.transition.id = transition_id
        future = self._change_state.call_async(request)
        assert wait_until(future.done)
        assert future.result().success
        assert expected_state == self.state()

    def configure(self):
        self.transition(Transition.TRANSITION_CONFIGURE, State.PRIMARY_STATE_INACTIVE)

    def activate(self):
        self.transition(Transition.TRANSITION_ACTIVATE, State.PRIMARY_STATE_ACTIVE)

    def deactivate(self):
        self.transition(Transition.TRANSITION_DEACTIVATE, State.PRIMARY_STATE_INACTIVE)

    def name_subscribers(self):
        return self.pub_name.get_subscription_count()


def wait_until(predicate, timeout=15.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.05)
    return predicate()


@pytest.fixture(scope='module', autouse=True)
def ros_context():
    # A domain of its own, shared with the nodes that the tests start.
    os.environ['ROS_DOMAIN_ID'] = str(os.getpid() % 100 + 100)
    os.environ['ROS_AUTOMATIC_DISCOVERY_RANGE'] = 'LOCALHOST'
    os.environ['RMW_IMPLEMENTATION'] = 'rmw_cyclonedds_cpp'
    rclpy.init()
    yield
    rclpy.shutdown()


@pytest.fixture
def greeter(request):
    executable, node_name, subscription_while_inactive = request.param
    path = Path(get_package_prefix(PACKAGE)) / 'lib' / PACKAGE / executable
    process = subprocess.Popen([path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    harness = Harness(node_name)
    try:
        yield harness, subscription_while_inactive
    finally:
        harness.close()
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


@pytest.mark.parametrize('greeter', GREETERS, indirect=True)
def test_greets_between_activation_and_deactivation(greeter):
    harness, _ = greeter
    assert State.PRIMARY_STATE_UNCONFIGURED == harness.state()
    harness.configure()
    assert not harness.greetings

    harness.activate()
    assert wait_until(lambda: 'hello everyone' in harness.greetings)
    assert wait_until(lambda: 'hello again' in harness.greetings)
    assert wait_until(lambda: harness.notifications)

    assert wait_until(lambda: harness.name_subscribers() > 0)
    harness.pub_name.publish(String(data='Ada'))
    assert wait_until(lambda: 'hello Ada' in harness.greetings)

    harness.deactivate()
    assert wait_until(lambda: 'goodbye' in harness.greetings)
    # A greeting that was already in flight may still arrive.
    time.sleep(1.0)
    settled = len(harness.greetings)
    time.sleep(1.5)
    assert settled == len(harness.greetings)


@pytest.mark.parametrize('greeter', GREETERS, indirect=True)
def test_subscription_exists_while_inactive_only_for_handwritten_node(greeter):
    harness, subscription_while_inactive = greeter
    harness.configure()
    if subscription_while_inactive:
        assert wait_until(lambda: harness.name_subscribers() > 0)
    else:
        time.sleep(1.5)
        assert 0 == harness.name_subscribers()

    harness.activate()
    assert wait_until(lambda: harness.name_subscribers() > 0)

    harness.deactivate()
    if subscription_while_inactive:
        time.sleep(1.5)
        assert harness.name_subscribers() > 0
    else:
        assert wait_until(lambda: 0 == harness.name_subscribers())
