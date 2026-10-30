# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Build, install and run the ``echo_robot`` package from the ``nodl_generator_py`` documentation.

The documentation includes the package's files, so this checks what it shows.
"""

import os
import signal
import subprocess
import time
from pathlib import Path

import pytest
import rclpy
from rclpy.node import Node
from std_msgs.msg import String

EXAMPLE_DIR = Path(__file__).parent.parent / 'nodl_generator_py' / 'doc' / 'examples' / 'echo_robot'
STARTUP_TIMEOUT_S = 30.0
EXIT_TIMEOUT_S = 15.0


def _run(command: list[str | Path], **kwargs) -> None:
    result = subprocess.run(command, capture_output=True, text=True, check=False, **kwargs)
    assert result.returncode == 0, f'{" ".join(map(str, command))}\n{result.stdout}\n{result.stderr}'


@pytest.fixture(scope='module')
def install_prefix(tmp_path_factory):
    root = tmp_path_factory.mktemp('echo_robot')
    prefix = root / 'install'
    _run(['cmake', '-S', EXAMPLE_DIR, '-B', root / 'build', f'-DCMAKE_INSTALL_PREFIX={prefix}'])
    _run(['cmake', '--build', root / 'build'])
    _run(['cmake', '--install', root / 'build'])
    return prefix


@pytest.fixture
def harness():
    rclpy.init()
    node = Node('echo_robot_harness')
    try:
        yield node
    finally:
        node.destroy_node()
        rclpy.shutdown()


def test_installed_executable_echoes_with_the_declared_parameter(install_prefix, harness):
    site_packages = next(install_prefix.glob('lib/python3*/site-packages'))
    environment = {
        **os.environ,
        'PYTHONPATH': os.pathsep.join(filter(None, [str(site_packages), os.environ.get('PYTHONPATH')])),
    }
    received = []
    harness.create_subscription(String, 'echo_out', lambda msg: received.append(msg.data), 10)
    publisher = harness.create_publisher(String, 'echo_in', 10)

    process = subprocess.Popen([install_prefix / 'lib' / 'echo_robot' / 'echo_node'], env=environment)
    try:
        deadline = time.monotonic() + STARTUP_TIMEOUT_S
        while not received:
            assert process.poll() is None, f'echo_node exited with {process.returncode}'
            assert time.monotonic() < deadline, 'no echo received'
            publisher.publish(String(data='hi'))
            rclpy.spin_once(harness, timeout_sec=0.2)

        assert 'hello: hi' == received[0]

        process.send_signal(signal.SIGINT)
        assert 0 == process.wait(timeout=EXIT_TIMEOUT_S)
    finally:
        if process.poll() is None:
            process.kill()
        process.wait()
