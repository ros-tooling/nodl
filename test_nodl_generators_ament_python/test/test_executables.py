# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Run the installed executables, which start a generated node and exit cleanly on SIGINT."""

import signal
import subprocess
import time
from pathlib import Path

import pytest
import rclpy
from ament_index_python.packages import get_package_prefix
from conftest import PACKAGE
from lifecycle_msgs.msg import State
from lifecycle_msgs.srv import GetState
from rclpy.node import Node
from std_msgs.msg import String

TIMEOUT_S = 15.0


def _executable(name: str) -> Path:
    return Path(get_package_prefix(PACKAGE)) / 'lib' / PACKAGE / name


@pytest.mark.parametrize('name', ['echo_node', 'lifecycle_node'])
def test_executable_is_the_generated_script_in_every_install_mode(name):
    script = _executable(name).read_text()

    assert 'pkg_resources' not in script
    assert 'run_node' in script


@pytest.fixture
def node_process(request):
    process = subprocess.Popen(
        [str(_executable(request.param))], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
    )
    yield process
    if process.poll() is None:
        process.kill()
    process.communicate()


def _spin_until(node, predicate, process):
    deadline = time.monotonic() + TIMEOUT_S
    while time.monotonic() < deadline and not predicate():
        assert process.poll() is None, process.communicate()[0]
        rclpy.spin_once(node, timeout_sec=0.1)
    return predicate()


def _stop(process):
    process.send_signal(signal.SIGINT)
    output, _ = process.communicate(timeout=TIMEOUT_S)
    assert 0 == process.returncode, output


@pytest.mark.parametrize('node_process', ['echo_node'], indirect=True)
def test_echo_node_comes_up_and_stops_on_sigint(ros_context, node_process):
    harness = Node('test_harness')
    received = []
    harness.create_subscription(String, '/echo_out', lambda msg: received.append(msg.data), 10)
    publisher = harness.create_publisher(String, '/echo_in', 10)
    try:
        assert _spin_until(harness, lambda: publisher.get_subscription_count() > 0, node_process)

        publisher.publish(String(data='ping'))

        assert _spin_until(harness, lambda: bool(received), node_process)
        assert ['hello: ping'] == received
        _stop(node_process)
    finally:
        harness.destroy_node()


@pytest.mark.parametrize('node_process', ['lifecycle_node'], indirect=True)
def test_lifecycle_node_comes_up_active_and_stops_on_sigint(ros_context, node_process):
    harness = Node('test_harness')
    client = harness.create_client(GetState, '/lifecycle_node/get_state')
    try:
        assert _spin_until(harness, client.service_is_ready, node_process)
        future = client.call_async(GetState.Request())
        assert _spin_until(harness, future.done, node_process)

        assert State.PRIMARY_STATE_ACTIVE == future.result().current_state.id
        _stop(node_process)
    finally:
        harness.destroy_node()
