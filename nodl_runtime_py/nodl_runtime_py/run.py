# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Run an rclpy node class as the main loop of an executable."""

from __future__ import annotations

import functools
import logging
import signal
import sys
import threading
from collections.abc import Callable
from types import FrameType

import rclpy
from rclpy.executors import Executor, ExternalShutdownException, ShutdownException, SingleThreadedExecutor
from rclpy.lifecycle import LifecycleNode, TransitionCallbackReturn
from rclpy.node import Node
from rclpy.signals import SignalHandlerOptions
from rclpy.utilities import ok, try_shutdown

# Bounds how long a stop request waits for the executor to wake up.
SPIN_PERIOD_S = 0.1

_Handler = Callable[[int, FrameType | None], object] | int | signal.Handlers

# What a second signal does: SIGINT raises KeyboardInterrupt and SIGTERM terminates the process.
_DEFAULT_HANDLERS = {
    signal.SIGINT: signal.default_int_handler,
    signal.SIGTERM: signal.SIG_DFL,
}

# The states a lifecycle node can be shut down from.
_SHUTDOWN_STATES = ('unconfigured', 'inactive', 'active')

_logger = logging.getLogger(__name__)


def run_node(
    node_class: Callable[[], Node],
    *,
    executor_class: Callable[[], Executor] = SingleThreadedExecutor,
    args: list[str] | None = None,
) -> int:
    """Construct and spin ``node_class()`` until SIGINT, SIGTERM or rclpy shutdown.

    ``node_class`` is called with no arguments, and is usually the node class itself.
    The loop ends normally, and ``run_node`` returns 0, after SIGINT, SIGTERM, or ``rclpy.shutdown()`` from any thread.

    rclpy's own signal handling is disabled, and SIGINT and SIGTERM request a stop instead.
    This avoids the ``RCLError: failed to initialize wait set`` that ``rclpy.spin`` can raise when a signal arrives during shutdown.
    A second signal restores the default behaviour, so a process stuck in a constructor, a callback or a cleanup can still be interrupted.
    The handlers installed before the call are restored when it returns.
    Because it installs signal handlers, it must be called from the main thread, and raises ``RuntimeError`` otherwise.

    A ``LifecycleNode`` is configured and activated after construction.
    A transition that does not succeed raises ``RuntimeError`` naming the node and the transition.
    On exit a lifecycle node is shut down, so its ``on_shutdown`` callback runs.
    This is skipped if the node is already finalized, or if rclpy was shut down, which stops the transition from being published.

    Exceptions from construction, transitions or callbacks propagate after cleanup.
    Cleanup shuts down the executor, shuts down the lifecycle node, destroys the node, then shuts down rclpy,
    and a step that fails does not skip the later ones.
    When the loop failed, errors in cleanup are logged and the original exception propagates.
    Otherwise the first error in cleanup propagates, and any others are logged.

    :param node_class: Callable that takes no arguments and returns the node.
    :param executor_class: Callable that takes no arguments and returns the executor to spin the node with,
        for example ``rclpy.executors.MultiThreadedExecutor``.
    :param args: Command line arguments for ``rclpy.init``, with the program name first like ``sys.argv``, which is the default.
    :return: The process exit code, 0 after a clean shutdown.
    """
    if threading.current_thread() is not threading.main_thread():
        raise RuntimeError('run_node must be called from the main thread, because it installs signal handlers')

    rclpy.init(args=sys.argv if args is None else args, signal_handler_options=SignalHandlerOptions.NO)
    stop = threading.Event()
    previous_handlers: dict[signal.Signals, _Handler] = {}
    executor = None
    node = None
    try:
        for sig in _DEFAULT_HANDLERS:
            # None means the handler was not installed from Python, which only SIG_DFL can restore.
            previous = signal.signal(sig, functools.partial(_request_stop, stop))
            previous_handlers[sig] = signal.SIG_DFL if previous is None else previous
        executor = executor_class()
        node = node_class()
        if isinstance(node, LifecycleNode):
            for transition in (node.trigger_configure, node.trigger_activate):
                result = transition()
                if TransitionCallbackReturn.SUCCESS != result:
                    raise RuntimeError(f'{node.get_name()}: {transition.__name__} returned {result.name}')
        executor.add_node(node)
        _spin(executor, stop)
    except BaseException:
        _clean_up(executor, node, previous_handlers, loop_failed=True)
        raise
    if error := _clean_up(executor, node, previous_handlers, loop_failed=False):
        raise error
    return 0


def _request_stop(stop: threading.Event, signum: int, frame: FrameType | None) -> None:
    stop.set()
    for sig, handler in _DEFAULT_HANDLERS.items():
        signal.signal(sig, handler)


def _spin(executor: Executor, stop: threading.Event) -> None:
    while ok() and not stop.is_set():
        try:
            executor.spin_once(timeout_sec=SPIN_PERIOD_S)
        except (ExternalShutdownException, ShutdownException):
            # Shutdown from another thread raises from spin_once before ok() is checked again.
            return


def _shutdown_lifecycle(node: LifecycleNode) -> None:
    # The transition publishes an event, which fails once rclpy has been shut down.
    if not ok():
        return
    # rclpy has no public accessor for the state, and trigger_shutdown raises from other states.
    if node._state_machine.current_state[1] not in _SHUTDOWN_STATES:
        return
    result = node.trigger_shutdown()
    if TransitionCallbackReturn.SUCCESS != result:
        raise RuntimeError(f'{node.get_name()}: trigger_shutdown returned {result.name}')


def _clean_up(
    executor: Executor | None,
    node: Node | None,
    previous_handlers: dict[signal.Signals, _Handler],
    *,
    loop_failed: bool,
) -> Exception | None:
    """Run every cleanup step, log the errors that will not propagate, and return the one that should."""
    # Restored first, so a signal during a cleanup that hangs is not swallowed by the stop request.
    for sig, handler in previous_handlers.items():
        signal.signal(sig, handler)

    steps: list[tuple[str, Callable[[], object]]] = []
    if executor is not None:
        steps.append(('executor shutdown', executor.shutdown))
    if isinstance(node, LifecycleNode):
        steps.append(('lifecycle shutdown', functools.partial(_shutdown_lifecycle, node)))
    if node is not None:
        steps.append(('node destroy', node.destroy_node))

    errors: list[tuple[str, Exception]] = []
    try:
        for name, step in steps:
            _attempt(name, step, errors)
    finally:
        _attempt('rclpy shutdown', try_shutdown, errors)

    for name, error in errors[0 if loop_failed else 1 :]:
        _logger.error('run_node cleanup failed in %s', name, exc_info=error)
    return None if loop_failed or not errors else errors[0][1]


def _attempt(name: str, step: Callable[[], object], errors: list[tuple[str, Exception]]) -> None:
    try:
        step()
    except Exception as error:
        errors.append((name, error))
