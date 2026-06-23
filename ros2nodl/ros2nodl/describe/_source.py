# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Acquire an observed Node from the live backend, YAML, or MCAP."""

from __future__ import annotations

import os
import subprocess
import time

_DEFAULT_TOPIC = '/nodl/observed_node'
_KEEPALIVE_SEC = 3.0


class SourceError(Exception):
    """A user-facing acquisition failure."""


def observe_binary():
    try:
        from ament_index_python.packages import get_package_prefix

        path = os.path.join(get_package_prefix('nodl_observe'), 'lib', 'nodl_observe', 'observe')
    except Exception:
        return None
    return path if os.path.isfile(path) else None


def _latched_qos():
    from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy

    return QoSProfile(
        depth=1,
        history=HistoryPolicy.KEEP_LAST,
        reliability=ReliabilityPolicy.RELIABLE,
        durability=DurabilityPolicy.TRANSIENT_LOCAL,
    )


def _wait_for_exit(process) -> None:
    try:
        process.wait(timeout=_KEEPALIVE_SEC + 2.0)
    except subprocess.TimeoutExpired:
        process.terminate()
        try:
            process.wait(timeout=2.0)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


def acquire_live(
    node_name: str,
    *,
    timeout_sec: float,
    include_parameters: bool = True,
    topic: str = _DEFAULT_TOPIC,
):
    binary = observe_binary()
    if binary is None:
        raise SourceError('the nodl_observe `observe` executable was not found; build/install nodl_observe.')

    import rclpy
    from rosgraph_msgs.msg import Node as NodeMsg

    command = [
        binary,
        node_name,
        '--timeout',
        repr(float(timeout_sec)),
        '--topic',
        topic,
        '--spin-seconds',
        repr(_KEEPALIVE_SEC),
    ]
    if not include_parameters:
        command.append('--no-parameters')
    process = subprocess.Popen(command, stderr=subprocess.PIPE, text=True)

    try:
        rclpy.init()
        owns_context = True
    except RuntimeError:
        owns_context = False

    received = []
    try:
        node = rclpy.create_node(f'_ros2nodl_describe_{os.getpid()}', start_parameter_services=False)
        try:
            node.create_subscription(NodeMsg, topic, received.append, _latched_qos())
            deadline = time.monotonic() + timeout_sec + _KEEPALIVE_SEC + 2.0
            while not received and time.monotonic() < deadline and process.poll() is None:
                rclpy.spin_once(node, timeout_sec=0.1)
            if received:
                return received[0]

            try:
                _, error = process.communicate(timeout=2.0)
            except subprocess.TimeoutExpired:
                process.terminate()
                _, error = process.communicate(timeout=2.0)
            raise SourceError(
                (error or '').strip() or f'timed out waiting for an observation of {node_name!r} on {topic!r}.'
            )
        finally:
            node.destroy_node()
    finally:
        if owns_context:
            rclpy.shutdown()
        _wait_for_exit(process)


def acquire_from_file(path: str, *, channel: str | None = None):
    if not os.path.isfile(path):
        raise SourceError(f'--from: file not found: {path}')
    extension = os.path.splitext(path)[1].lower()
    if extension in ('.yaml', '.yml'):
        return _load_yaml(path)
    if extension == '.mcap':
        return _load_mcap(path, channel)
    raise SourceError(f'--from: unrecognised extension "{extension}"; use .yaml, .yml, or .mcap')


def _load_yaml(path: str):
    import yaml
    from rosgraph_msgs.msg import Node
    from rosidl_runtime_py.set_message import set_message_fields

    try:
        with open(path) as source:
            data = yaml.safe_load(source)
        if not isinstance(data, dict):
            raise ValueError('expected a YAML mapping')
        message = Node()
        set_message_fields(message, data)
        return message
    except Exception as exc:
        raise SourceError(f'--from: {path} does not match rosgraph_msgs/Node: {exc}') from exc


def _load_mcap(path: str, channel: str | None):
    try:
        from mcap.reader import make_reader
    except ImportError as exc:
        raise SourceError("--from: reading .mcap requires the 'mcap' package") from exc
    from rclpy.serialization import deserialize_message
    from rosgraph_msgs.msg import Node

    try:
        with open(path, 'rb') as source:
            available = []
            for _, message_channel, message in make_reader(source).iter_messages():
                available.append(message_channel.topic)
                if channel is None or message_channel.topic == channel:
                    return deserialize_message(message.data, Node)
    except Exception as exc:
        raise SourceError(f'--from: could not read {path}: {exc}') from exc
    if channel is not None:
        raise SourceError(f'--from: channel {channel!r} not found; available: {sorted(set(available))}')
    raise SourceError(f'--from: no messages found in {path}')
