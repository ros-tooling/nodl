# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Exercise runtime conformance through the commands shown in the tutorial."""

import os
import shutil
import subprocess
from contextlib import contextmanager
from pathlib import Path

from ament_index_python.packages import get_package_prefix, get_package_share_directory

PACKAGE = 'nodl_tutorial_basics'
NODE_NAME = '/talker'


def _test_environment():
    environment = os.environ.copy()
    environment['ROS_DOMAIN_ID'] = str(os.getpid() % 100 + 100)
    environment['ROS_AUTOMATIC_DISCOVERY_RANGE'] = 'LOCALHOST'
    environment['RMW_IMPLEMENTATION'] = 'rmw_cyclonedds_cpp'
    return environment


def _node_executable():
    prefix = Path(get_package_prefix(PACKAGE))
    return prefix / 'lib' / PACKAGE / 'talker_cpp'


def _contract():
    share = Path(get_package_share_directory(PACKAGE))
    return share / 'nodl' / 'talker.nodl.yaml'


# Each case owns one node and makes one CLI assertion, so a context manager keeps
# the lifecycle clearer than a launch_testing description would.
@contextmanager
def _running_node(*node_arguments):
    node = subprocess.Popen(
        [_node_executable(), *node_arguments],
        env=_test_environment(),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        yield
    finally:
        node.terminate()
        try:
            node.wait(timeout=5)
        except subprocess.TimeoutExpired:
            node.kill()
            node.wait()


def _run_conform(*node_arguments):
    ros2 = shutil.which('ros2')
    assert ros2 is not None

    with _running_node(*node_arguments):
        return subprocess.run(
            [ros2, 'nodl', 'conform', NODE_NAME, '--file', _contract(), '--timeout', '10'],
            env=_test_environment(),
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )


def test_generated_node_conforms():
    result = _run_conform()

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == f'{NODE_NAME}: conforms'


def test_remapped_topic_does_not_conform():
    result = _run_conform('--ros-args', '-r', 'chatter:=chatter_regressed')

    assert result.returncode != 0
    assert "[missing] publishers '/chatter'" in result.stderr
    assert "[extra] publishers '/chatter_regressed'" in result.stderr
