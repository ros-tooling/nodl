# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Exercise the runnable tutorial servers and the commands documented for them."""

import os
import shutil
import subprocess
import time
from contextlib import contextmanager
from pathlib import Path

import pytest
import rclpy
from action_msgs.msg import GoalStatus
from ament_index_python.packages import get_package_prefix, get_package_share_directory
from example_interfaces.action import Fibonacci
from rclpy.action import ActionClient
from rclpy.executors import SingleThreadedExecutor
from rclpy.node import Node

PACKAGE = 'nodl_tutorial_lifecycle_action'
LIFECYCLE_SERVERS = (
    ('fibonacci_action_server_cpp', '/fibonacci_action_server_cpp'),
    ('fibonacci_action_server_py', '/fibonacci_action_server_py'),
)


@pytest.fixture(autouse=True)
def isolated_ros_graph(monkeypatch):
    monkeypatch.setenv('ROS_DOMAIN_ID', str(os.getpid() % 100 + 100))
    monkeypatch.setenv('ROS_AUTOMATIC_DISCOVERY_RANGE', 'LOCALHOST')
    monkeypatch.setenv('RMW_IMPLEMENTATION', 'rmw_cyclonedds_cpp')


def _executable(name):
    return Path(get_package_prefix(PACKAGE)) / 'lib' / PACKAGE / name


def _conformance_document():
    return Path(get_package_share_directory(PACKAGE)) / 'nodl' / 'fibonacci_codegen.nodl.yaml'


@contextmanager
def _running_server(executable):
    server = subprocess.Popen(
        [_executable(executable)],
        env=os.environ.copy(),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        yield
    finally:
        server.terminate()
        try:
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait()


def _run_cli(*arguments, timeout=15):
    ros2 = shutil.which('ros2')
    assert ros2 is not None
    return subprocess.run(
        [ros2, *arguments],
        env=os.environ.copy(),
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def _wait_for_lifecycle(node_name, timeout=10.0):
    deadline = time.monotonic() + timeout
    last_result = None
    while time.monotonic() < deadline:
        last_result = _run_cli('lifecycle', 'get', node_name, timeout=5)
        if last_result.returncode == 0:
            return last_result.stdout.split()[0]
        time.sleep(0.1)
    pytest.fail(f'lifecycle node did not become ready: {last_result}')


def _set_transition(node_name, transition, expected_state):
    result = _run_cli('lifecycle', 'set', node_name, transition)
    assert result.returncode == 0, result.stderr
    assert _wait_for_lifecycle(node_name) == expected_state


def _spin_until(executor, predicate, timeout=10.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline and not predicate():
        executor.spin_once(timeout_sec=0.05)
    assert predicate()


def _send_goal(executor, client, order, feedback=None):
    future = client.send_goal_async(Fibonacci.Goal(order=order), feedback_callback=feedback)
    _spin_until(executor, future.done)
    return future.result()


@pytest.mark.parametrize('executable,node_name', LIFECYCLE_SERVERS)
def test_lifecycle_action_server(executable, node_name):
    with _running_server(executable):
        assert _wait_for_lifecycle(node_name) == 'unconfigured'

        conform = _run_cli(
            'nodl',
            'conform',
            node_name,
            '--file',
            str(_conformance_document()),
            '--timeout',
            '10',
            timeout=20,
        )
        assert conform.returncode == 0, conform.stderr
        assert conform.stdout.strip() == f'{node_name}: conforms'

        rclpy.init()
        harness = Node(f'{node_name.removeprefix("/")}__test_harness')
        executor = SingleThreadedExecutor()
        executor.add_node(harness)
        client = ActionClient(harness, Fibonacci, '/fibonacci')
        try:
            assert client.wait_for_server(timeout_sec=5.0)
            assert not _send_goal(executor, client, 5).accepted

            _set_transition(node_name, 'configure', 'inactive')
            _set_transition(node_name, 'activate', 'active')

            feedback_sequences = []
            goal = _send_goal(
                executor,
                client,
                5,
                lambda message: feedback_sequences.append(list(message.feedback.sequence)),
            )
            assert goal.accepted
            result_future = goal.get_result_async()
            _spin_until(executor, result_future.done)
            assert result_future.result().status == GoalStatus.STATUS_SUCCEEDED
            assert list(result_future.result().result.sequence) == [0, 1, 1, 2, 3, 5]
            assert feedback_sequences

            cancel_goal = _send_goal(executor, client, 100)
            assert cancel_goal.accepted
            time.sleep(0.2)
            cancel_future = cancel_goal.cancel_goal_async()
            _spin_until(executor, cancel_future.done)
            assert cancel_future.result().goals_canceling
            canceled_result = cancel_goal.get_result_async()
            _spin_until(executor, canceled_result.done)
            assert canceled_result.result().status == GoalStatus.STATUS_CANCELED

            _set_transition(node_name, 'deactivate', 'inactive')
            assert not _send_goal(executor, client, 5).accepted
            _set_transition(node_name, 'cleanup', 'unconfigured')
        finally:
            executor.shutdown()
            harness.destroy_node()
            rclpy.shutdown()
