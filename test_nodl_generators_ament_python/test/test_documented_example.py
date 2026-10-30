# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Build, install, test and run the ``echo_robot_py`` package from the ``nodl_generator_py`` documentation.

The documentation includes the package's files, so this checks what it shows.
It copies the package, so nothing is written next to the documentation.
"""

import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest
import rclpy
from rclpy.node import Node
from std_msgs.msg import String

EXAMPLE_DIR = Path(__file__).resolve().parents[2] / 'nodl_generator_py' / 'doc' / 'examples' / 'echo_robot_py'
STARTUP_TIMEOUT_S = 30.0
EXIT_TIMEOUT_S = 15.0


def _run(command, **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(command, capture_output=True, text=True, check=False, **kwargs)


def _install(root: Path, source: Path):
    """Install the package in ``source`` as colcon does, and return the install layout."""
    (root / 'egg').mkdir()
    layout = {name: root / 'install' / name for name in ('lib', 'scripts', 'data')}
    result = _run(
        [
            sys.executable,
            'setup.py',
            'egg_info',
            '--egg-base',
            root / 'egg',
            'build',
            '--build-base',
            root / 'build',
            'install',
            '--install-lib',
            layout['lib'],
            '--install-scripts',
            layout['scripts'],
            '--install-data',
            layout['data'],
            '--single-version-externally-managed',
            '--record',
            root / 'install.log',
        ],
        cwd=source,
    )
    assert 0 == result.returncode, result.stderr
    return layout


@pytest.fixture(scope='module')
def example(tmp_path_factory):
    """Install a copy of the example, and return its source directory and the install layout."""
    root = tmp_path_factory.mktemp('echo_robot_py')
    source = root / 'src'
    shutil.copytree(EXAMPLE_DIR, source)
    return source, _install(root, source)


def _pytest(source: Path, layout, *arguments: str) -> subprocess.CompletedProcess:
    environment = {
        **os.environ,
        'PYTHONPATH': os.pathsep.join(filter(None, [str(layout['lib']), os.environ.get('PYTHONPATH')])),
    }
    return _run([sys.executable, '-m', 'pytest', '-p', 'no:cacheprovider', *arguments], cwd=source, env=environment)


def test_example_tests_pass_against_the_built_package(example):
    source, layout = example

    result = _pytest(source, layout)

    assert 0 == result.returncode, result.stdout


def test_example_tests_need_the_conftest(example):
    source, layout = example

    result = _pytest(source, layout, '--noconftest')

    assert 0 != result.returncode
    assert "No module named 'echo_robot_py.generated'" in result.stdout


def test_example_tests_need_a_test_directory_without_an_init_file(example, tmp_path):
    source, layout = example
    copy = tmp_path / 'copy'
    shutil.copytree(source, copy)
    (copy / 'test' / '__init__.py').touch()

    result = _pytest(copy, layout)

    assert 0 != result.returncode
    assert "No module named 'echo_robot_py.generated'" in result.stdout


def test_src_layout_does_not_need_the_conftest_or_mind_a_test_init_file(tmp_path):
    source = tmp_path / 'source'
    shutil.copytree(EXAMPLE_DIR, source)
    (source / 'src').mkdir()
    shutil.move(source / 'echo_robot_py', source / 'src' / 'echo_robot_py')
    (source / 'test' / 'conftest.py').unlink()
    (source / 'test' / '__init__.py').touch()
    setup_py = (source / 'setup.py').read_text()
    (source / 'setup.py').write_text(
        setup_py.replace(
            "find_packages(exclude=['test', 'test.*'])", "find_packages(where='src'),\n    package_dir={'': 'src'}"
        )
    )
    layout = _install(tmp_path, source)

    result = _pytest(source, layout)

    assert 0 == result.returncode, result.stdout


def test_example_does_not_write_to_the_source_tree(example):
    source, _ = example

    assert not list(source.rglob('generated'))
    assert not list(source.rglob('*_parameters.*'))


@pytest.fixture
def harness():
    rclpy.init()
    node = Node('echo_robot_py_harness')
    try:
        yield node
    finally:
        node.destroy_node()
        rclpy.shutdown()


def test_installed_executable_echoes_with_the_declared_parameter(example, harness):
    _, layout = example
    environment = {
        **os.environ,
        'PYTHONPATH': os.pathsep.join(filter(None, [str(layout['lib']), os.environ.get('PYTHONPATH')])),
    }
    received = []
    harness.create_subscription(String, 'echo_out', lambda msg: received.append(msg.data), 10)
    publisher = harness.create_publisher(String, 'echo_in', 10)

    process = subprocess.Popen([layout['scripts'] / 'echo_node'], env=environment)
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
