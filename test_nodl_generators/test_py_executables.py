# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Run the executables that ``nodl_add_py_executable`` installs, as ``ros2 run`` would."""

import os
import signal
import subprocess
import time
from pathlib import Path

import pytest
import rclpy
from lifecycle_msgs.msg import State
from lifecycle_msgs.srv import GetState
from rclpy.node import Node
from ros2pkg.api import get_executable_paths

from test_nodl_generators.recording_executor import MARKER_ENVIRONMENT_VARIABLE

PACKAGE = 'test_nodl_generators'
EXECUTABLES = {Path(path).name: path for path in get_executable_paths(package_name=PACKAGE)}
STARTUP_TIMEOUT_S = 30.0
EXIT_TIMEOUT_S = 15.0


@pytest.fixture
def harness():
    rclpy.init()
    node = Node('py_executable_harness')
    try:
        yield node
    finally:
        node.destroy_node()
        rclpy.shutdown()


@pytest.fixture
def start_executable(harness):
    """Start an executable that ``ros2 run`` can find, under a unique node name, and wait for the node to appear."""
    processes = []

    def start(executable: str, environment: dict[str, str] | None = None) -> tuple[subprocess.Popen, str]:
        node_name = f'{executable}_under_test'
        process = subprocess.Popen(
            [EXECUTABLES[executable], '--ros-args', '-r', f'__node:={node_name}'],
            env={**os.environ, **(environment or {})},
        )
        processes.append(process)
        deadline = time.monotonic() + STARTUP_TIMEOUT_S
        while node_name not in harness.get_node_names():
            assert process.poll() is None, f'{executable} exited with {process.returncode} before its node appeared'
            assert time.monotonic() < deadline, f'node {node_name} did not appear'
            time.sleep(0.1)
        return process, node_name

    yield start
    for process in processes:
        if process.poll() is None:
            process.kill()
        process.wait()


@pytest.mark.parametrize('executable', ['py_minimal_node', 'py_lifecycle_node', 'py_recording_node'])
def test_ros2_run_finds_the_executable(executable):
    assert executable in EXECUTABLES


@pytest.mark.parametrize('stop_signal', [signal.SIGINT, signal.SIGTERM])
def test_minimal_node_runs_until_signalled(start_executable, stop_signal):
    process, _ = start_executable('py_minimal_node')

    process.send_signal(stop_signal)

    assert 0 == process.wait(timeout=EXIT_TIMEOUT_S)


def test_lifecycle_node_is_activated_and_stops_on_sigint(harness, start_executable):
    process, node_name = start_executable('py_lifecycle_node')
    client = harness.create_client(GetState, f'/{node_name}/get_state')
    assert client.wait_for_service(timeout_sec=STARTUP_TIMEOUT_S)

    future = client.call_async(GetState.Request())
    rclpy.spin_until_future_complete(harness, future, timeout_sec=EXIT_TIMEOUT_S)
    assert future.done()
    assert State.PRIMARY_STATE_ACTIVE == future.result().current_state.id

    process.send_signal(signal.SIGINT)

    assert 0 == process.wait(timeout=EXIT_TIMEOUT_S)


def test_executor_option_selects_the_executor(start_executable, tmp_path):
    marker = tmp_path / 'executor_marker'
    process, _ = start_executable('py_recording_node', {MARKER_ENVIRONMENT_VARIABLE: str(marker)})

    assert 'constructed' == marker.read_text()

    process.send_signal(signal.SIGINT)

    assert 0 == process.wait(timeout=EXIT_TIMEOUT_S)
