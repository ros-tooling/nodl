# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0

import signal
import threading
from pathlib import Path

import fixture_nodes
import pytest
from rclpy.utilities import ok

from nodl_runtime_py import run_node

EXAMPLES_DIR = Path(__file__).parent.parent / 'doc' / 'examples'

EXECUTABLE = """\
import sys

from fixture_nodes import {node_class}
from nodl_runtime_py import run_node
from rclpy.executors import {executor_class}

sys.exit(run_node({node_class}, executor_class={executor_class}, args={args!r}))
"""


@pytest.fixture
def start_node(tmp_path, run_script):
    def start(node_class, executor_class='SingleThreadedExecutor', args=None):
        script = tmp_path / f'{node_class}.py'
        script.write_text(EXECUTABLE.format(node_class=node_class, executor_class=executor_class, args=args))
        return run_script(script)

    return start


# Repeated to cover the shutdown race between the signal and spin, which the stock rclpy.spin loses about 3% of the time.
@pytest.mark.parametrize('attempt', range(20))
def test_sigint_exits_cleanly(start_node, attempt):
    node = start_node('ReadyNode')
    node.wait_ready()
    code, output = node.stop(signal.SIGINT)
    assert 0 == code, output


def test_sigterm_exits_cleanly(start_node):
    node = start_node('ReadyNode')
    node.wait_ready()
    code, output = node.stop(signal.SIGTERM)
    assert 0 == code, output


@pytest.mark.parametrize('executor_class', ['SingleThreadedExecutor', 'MultiThreadedExecutor'])
def test_executor_class(start_node, executor_class):
    node = start_node('ReadyNode', executor_class)
    assert f'ready {executor_class}' == node.wait_ready()
    code, output = node.stop()
    assert 0 == code, output


def test_lifecycle_node_is_activated(start_node):
    node = start_node('ActivatedNode')
    node.wait_ready()
    code, output = node.stop()
    assert 0 == code, output


def test_lifecycle_node_is_shut_down_on_exit(start_node):
    node = start_node('ShutdownHookNode')
    node.wait_ready()
    code, output = node.stop()
    assert 0 == code, output
    assert fixture_nodes.SHUTDOWN in output


@pytest.mark.parametrize(
    'node_class, message',
    [
        ('FailingConfigureNode', 'failing_configure_node: trigger_configure returned FAILURE'),
        ('FailingActivateNode', 'failing_activate_node: trigger_activate returned FAILURE'),
    ],
)
def test_failed_lifecycle_transition_raises(start_node, node_class, message):
    code, output = start_node(node_class).finish()
    assert 0 != code
    assert message in output


def test_rclpy_shutdown_from_node_exits_cleanly(start_node):
    code, output = start_node('SelfShutdownNode').finish()
    assert 0 == code, output


# Repeated because spin_once raises from the thread's shutdown only if it is waiting when it happens.
@pytest.mark.parametrize('attempt', range(5))
def test_rclpy_shutdown_from_thread_exits_cleanly(start_node, attempt):
    code, output = start_node('ThreadShutdownNode').finish()
    assert 0 == code, output


def test_lifecycle_node_exits_cleanly_after_rclpy_shutdown(start_node):
    code, output = start_node('ThreadShutdownLifecycleNode').finish()
    assert 0 == code, output
    assert fixture_nodes.SHUTDOWN not in output


def test_constructor_exception_propagates(start_node):
    code, output = start_node('RaisingNode').finish()
    assert 0 != code
    assert 'fixture constructor failure' in output


@pytest.mark.parametrize('sig', [signal.SIGINT, signal.SIGTERM])
@pytest.mark.parametrize('node_class', ['BlockingCallbackNode', 'BlockingConstructorNode'])
def test_second_signal_interrupts_blocked_node(start_node, node_class, sig):
    node = start_node(node_class)
    node.wait_ready()
    code, output = node.stop_with_repeated(sig)
    assert 0 != code, output


def test_failed_callback_is_not_masked_by_failed_cleanup(start_node):
    code, output = start_node('CallbackAndDestroyRaiseNode').finish()
    assert 0 != code
    assert 'fixture cleanup failure' in output
    assert 'RuntimeError: fixture callback failure' == output.splitlines()[-1]
    assert 1 == output.count('run_node cleanup failed')
    assert fixture_nodes.CONTEXT_SHUTDOWN in output


def test_failed_cleanup_raises_after_clean_shutdown(start_node):
    node = start_node('DestroyRaisesNode')
    node.wait_ready()
    code, output = node.stop()
    assert 0 != code
    assert 'RuntimeError: fixture cleanup failure' == output.splitlines()[-1]
    assert 0 == output.count('run_node cleanup failed')
    assert fixture_nodes.CONTEXT_SHUTDOWN in output


def test_args_are_passed_to_rclpy(start_node):
    node = start_node('ParameterNode', args=['program', '--ros-args', '-p', 'greeting:=explicit'])
    assert 'ready explicit' == node.wait_ready()
    code, output = node.stop()
    assert 0 == code, output


def test_args_default_to_sys_argv(run_script):
    node = run_script(EXAMPLES_DIR / 'greeter.py', ['--ros-args', '-p', 'greeting:=Goodbye'])
    node.wait_ready('Goodbye, world')
    code, output = node.stop()
    assert 0 == code, output


@pytest.mark.parametrize('example', ['greeter.py', 'greeter_multithreaded.py'])
def test_examples_run(run_script, example):
    node = run_script(EXAMPLES_DIR / example)
    node.wait_ready('Hello, world')
    code, output = node.stop()
    assert 0 == code, output


def test_requires_main_thread():
    errors = []

    def call():
        try:
            run_node(fixture_nodes.ReadyNode)
        except RuntimeError as error:
            errors.append(str(error))

    thread = threading.Thread(target=call)
    thread.start()
    thread.join()
    assert 1 == len(errors)
    assert 'must be called from the main thread' in errors[0]
    assert not ok()


def test_failing_executor_class_leaves_rclpy_shut_down():
    def raising_executor():
        raise RuntimeError('fixture executor failure')

    with pytest.raises(RuntimeError, match='fixture executor failure'):
        run_node(fixture_nodes.ReadyNode, executor_class=raising_executor)
    assert not ok()


@pytest.mark.parametrize('node_class', [fixture_nodes.SelfShutdownNode, fixture_nodes.RaisingNode])
def test_signal_handlers_are_restored(node_class):
    handlers = {sig: signal.getsignal(sig) for sig in (signal.SIGINT, signal.SIGTERM)}
    try:
        run_node(node_class)
    except RuntimeError:
        pass
    assert handlers == {sig: signal.getsignal(sig) for sig in handlers}


def test_handler_not_installed_from_python_is_restored_as_default(monkeypatch):
    original = {sig: signal.getsignal(sig) for sig in (signal.SIGINT, signal.SIGTERM)}
    install = signal.signal

    def install_returning_none(sig, handler):
        install(sig, handler)

    monkeypatch.setattr(signal, 'signal', install_returning_none)
    try:
        run_node(fixture_nodes.SelfShutdownNode)
        assert {sig: signal.SIG_DFL for sig in original} == {sig: signal.getsignal(sig) for sig in original}
    finally:
        for sig, handler in original.items():
            install(sig, handler)
