# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Helpers that gate a subscription or a service on an activation gate, see the ``nodl_runtime_py`` overview."""

from __future__ import annotations

import inspect
from collections.abc import Callable
from typing import Any

from rclpy.lifecycle import SimpleManagedEntity
from rclpy.node import Node
from rclpy.service import Service


class _Dropped:
    """Marks a service request that was dropped, so that no response is sent."""


_DROPPED = _Dropped()


def gate_subscription_callback(gate: SimpleManagedEntity, callback: Callable[[Any], Any]) -> Callable[[Any], Any]:
    """Wrap a subscription callback so that messages are dropped while ``gate`` is closed.

    The result is passed to ``Node.create_subscription`` in place of ``callback``.
    A coroutine function callback is wrapped in a coroutine function.

    :param gate: The activation gate.
    :param callback: The callback that takes the message.
    :return: A callback that calls ``callback`` only while the gate is open.
    """
    if inspect.iscoroutinefunction(callback):

        async def gated_async(msg: Any) -> Any:
            if gate.is_activated:
                return await callback(msg)

        return gated_async

    def gated(msg: Any) -> Any:
        if gate.is_activated:
            return callback(msg)

    return gated


def create_gated_service(
    node: Node,
    gate: SimpleManagedEntity,
    srv_type: Any,
    srv_name: str,
    callback: Callable[[Any, Any], Any],
    **kwargs: Any,
) -> Service:
    """Create a service server that drops requests while ``gate`` is closed.

    A dropped request gets no response and does not run ``callback``, and its client keeps waiting.
    rclpy always sends the value a service callback returns,
    so the returned service has its ``send_response`` replaced on the instance to skip dropped requests.
    A coroutine function callback is wrapped in a coroutine function.

    :param node: The node that creates the service.
    :param gate: The activation gate.
    :param srv_type: The service type.
    :param srv_name: The name of the service.
    :param callback: The callback that takes the request and the response to fill in, and returns the response.
    :param kwargs: Passed to ``Node.create_service``, for example ``qos_profile`` or ``callback_group``.
    :return: The service.
    """
    if inspect.iscoroutinefunction(callback):

        async def gated_async(request: Any, response: Any) -> Any:
            return await callback(request, response) if gate.is_activated else _DROPPED

        gated_callback: Callable[[Any, Any], Any] = gated_async
    else:

        def gated_sync(request: Any, response: Any) -> Any:
            return callback(request, response) if gate.is_activated else _DROPPED

        gated_callback = gated_sync

    service = node.create_service(srv_type, srv_name, gated_callback, **kwargs)
    send_response = service.send_response

    def send_unless_dropped(response: Any, header: Any) -> None:
        if response is not _DROPPED:
            send_response(response, header)

    setattr(service, 'send_response', send_unless_dropped)
    return service
