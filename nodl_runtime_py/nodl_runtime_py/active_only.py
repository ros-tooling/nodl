# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Helpers that block a subscription's messages, a service's requests, a client's requests and goals, or an action server's goals, while an activation gate is closed, see the ``nodl_runtime_py`` overview."""

from __future__ import annotations

import inspect
import threading
from collections.abc import Callable
from typing import Any

from rclpy.action.client import ActionClient
from rclpy.action.server import (
    ActionServer,
    CancelResponse,
    GoalResponse,
    ServerGoalHandle,
    default_cancel_callback,
    default_goal_callback,
)
from rclpy.client import Client
from rclpy.lifecycle import SimpleManagedEntity
from rclpy.node import Node
from rclpy.service import Service
from rclpy.task import Future


class InactiveError(RuntimeError):
    """Raised by an active-only client that blocks a request or goal while its gate is closed."""


class _Dropped:
    """Marks a service request that was dropped, so that no response is sent."""


_DROPPED = _Dropped()


def active_only_subscription_callback(
    gate: SimpleManagedEntity, callback: Callable[[Any], Any]
) -> Callable[[Any], Any]:
    """Wrap a subscription callback so that messages are dropped while ``gate`` is closed.

    The result is passed to ``Node.create_subscription`` in place of ``callback``.
    A coroutine function callback is wrapped in a coroutine function.

    :param gate: The activation gate.
    :param callback: The callback that takes the message.
    :return: A callback that calls ``callback`` when the gate is open and drops the message otherwise.
    """
    if inspect.iscoroutinefunction(callback):

        async def active_only_async(msg: Any) -> Any:
            if gate.is_activated:
                return await callback(msg)

        return active_only_async

    def active_only(msg: Any) -> Any:
        if gate.is_activated:
            return callback(msg)

    return active_only


def create_active_only_service(
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

        async def active_only_async(request: Any, response: Any) -> Any:
            return await callback(request, response) if gate.is_activated else _DROPPED

        active_only_callback: Callable[[Any, Any], Any] = active_only_async
    else:

        def active_only_sync(request: Any, response: Any) -> Any:
            return callback(request, response) if gate.is_activated else _DROPPED

        active_only_callback = active_only_sync

    service = node.create_service(srv_type, srv_name, active_only_callback, **kwargs)
    send_response = service.send_response

    def send_unless_dropped(response: Any, header: Any) -> None:
        if response is not _DROPPED:
            send_response(response, header)

    setattr(service, 'send_response', send_unless_dropped)
    return service


class ActiveOnlyClient:
    """A service client that blocks ``call_async`` with ``InactiveError`` while its gate is closed.

    The ``client`` property returns the wrapped client, see the ``nodl_runtime_py`` overview.
    """

    def __init__(self, gate: SimpleManagedEntity, client: Client) -> None:
        """Wrap ``client``, which the node created with ``Node.create_client``.

        :param gate: The activation gate.
        :param client: The client to gate.
        """
        self._gate = gate
        self._client = client

    @property
    def client(self) -> Client:
        """The wrapped client, for anything the wrapper does not expose."""
        return self._client

    def call_async(self, request: Any) -> Future:
        """Send a request and return the future of its response.

        :param request: The service request.
        :return: A future that completes with the response.
        :raises InactiveError: When the gate is closed.
        """
        if not self._gate.is_activated:
            raise InactiveError(f'cannot call service {self._client.srv_name}: the node is not active')
        return self._client.call_async(request)

    def service_is_ready(self) -> bool:
        """Return whether a server is ready, whether or not the gate is open."""
        return self._client.service_is_ready()

    def wait_for_service(self, timeout_sec: float | None = None) -> bool:
        """Wait for a server to become ready, whether or not the gate is open.

        :param timeout_sec: Seconds to wait, or ``None`` to wait forever.
        :return: ``True`` if a server is ready, ``False`` on a timeout.
        """
        return self._client.wait_for_service(timeout_sec)


class ActiveOnlyActionClient:
    """An action client that blocks ``send_goal_async`` with ``InactiveError`` while its gate is closed.

    The ``client`` property returns the wrapped client, see the ``nodl_runtime_py`` overview.
    """

    def __init__(self, gate: SimpleManagedEntity, client: ActionClient) -> None:
        """Wrap ``client``, which the caller created with ``rclpy.action.ActionClient``.

        :param gate: The activation gate.
        :param client: The client to gate.
        """
        self._gate = gate
        self._client = client

    @property
    def client(self) -> ActionClient:
        """The wrapped client, for anything the wrapper does not expose."""
        return self._client

    def send_goal_async(self, goal: Any, **kwargs: Any) -> Future:
        """Send a goal and return the future of its goal handle.

        :param goal: The goal request.
        :param kwargs: Passed to ``ActionClient.send_goal_async``, for example ``feedback_callback``.
        :return: A future that completes with the goal handle.
        :raises InactiveError: When the gate is closed.
        """
        if not self._gate.is_activated:
            raise InactiveError('cannot send a goal: the node is not active')
        return self._client.send_goal_async(goal, **kwargs)

    def server_is_ready(self) -> bool:
        """Return whether a server is ready, whether or not the gate is open."""
        return self._client.server_is_ready()

    def wait_for_server(self, timeout_sec: float | None = None) -> bool:
        """Wait for a server to become ready, whether or not the gate is open.

        :param timeout_sec: Seconds to wait, or ``None`` to wait forever.
        :return: ``True`` if a server is ready, ``False`` on a timeout.
        """
        return self._client.wait_for_server(timeout_sec)


class ActiveOnlyActionServer(SimpleManagedEntity):
    """An action server that lets a lifecycle node reject goals while it is inactive and end its active goals when it deactivates.

    The server is a managed entity, so register it with ``add_managed_entity``.
    ``on_deactivate`` becomes inactive first, then ends each recorded goal that is still active:
    ``abort()`` for executing goals and ``canceled()`` for canceling goals.
    A call that fails because the goal went terminal is skipped, and one that fails while the goal is still active is retried once.
    See the ``nodl_runtime_py`` overview for the goal state table and what execute callbacks must check.
    """

    def __init__(
        self,
        node: Node,
        action_type: Any,
        action_name: str,
        execute_callback: Callable[[ServerGoalHandle], Any],
        *,
        goal_callback: Callable[[Any], GoalResponse] = default_goal_callback,
        cancel_callback: Callable[[ServerGoalHandle], CancelResponse] = default_cancel_callback,
        **kwargs: Any,
    ) -> None:
        """Create the action server on ``node``, which executes each accepted goal at once.

        :param node: The node that owns the action server.
        :param action_type: The action type.
        :param action_name: The name of the action.
        :param execute_callback: Called to execute each accepted goal.
        :param goal_callback: Called for each goal sent while the server is active.
        :param cancel_callback: Called for each cancel request.
        :param kwargs: Passed to ``rclpy.action.ActionServer``, for example ``callback_group`` or ``result_timeout``.
        """
        super().__init__()
        self._action_type = action_type
        self._lock = threading.Lock()
        self._goals: dict[bytes, ServerGoalHandle] = {}
        self._server = ActionServer(
            node,
            action_type,
            action_name,
            execute_callback,
            goal_callback=self._active_only_goal_callback(goal_callback),
            cancel_callback=cancel_callback,
            handle_accepted_callback=self._on_accepted,
            **kwargs,
        )

    @property
    def server(self) -> ActionServer:
        """The wrapped action server, for anything the wrapper does not expose."""
        return self._server

    def on_deactivate(self, state: Any) -> Any:
        """Become inactive, then end every recorded goal that is still active."""
        result = super().on_deactivate(state)
        with self._lock:
            goals = list(self._goals.values())
            self._goals.clear()
        for goal_handle in goals:
            self._end_goal(goal_handle)
        return result

    def _active_only_goal_callback(self, callback: Callable[[Any], GoalResponse]) -> Callable[[Any], Any]:
        if inspect.iscoroutinefunction(callback):

            async def active_only_async(goal_request: Any) -> GoalResponse:
                return await callback(goal_request) if self.is_activated else GoalResponse.REJECT

            return active_only_async

        def active_only(goal_request: Any) -> GoalResponse:
            return callback(goal_request) if self.is_activated else GoalResponse.REJECT

        return active_only

    def _on_accepted(self, goal_handle: ServerGoalHandle) -> None:
        # Recording and executing happen under the lock, so a deactivation that is ending goals only sees executing goals.
        with self._lock:
            if self.is_activated:
                self._goals = {key: goal for key, goal in self._goals.items() if goal.is_active}
                self._goals[bytes(goal_handle.goal_id.uuid)] = goal_handle
                goal_handle.execute()
                return
        # The server deactivated after it accepted the goal, so the goal ends itself instead of reaching the author.
        goal_handle.execute(self._end_goal_and_return_result)

    def _end_goal_and_return_result(self, goal_handle: ServerGoalHandle) -> Any:
        self._end_goal(goal_handle)
        return self._action_type.Result()

    @staticmethod
    def _end_goal(goal_handle: ServerGoalHandle) -> None:
        """End a goal, retrying once when a call fails but the goal is still active."""
        for _ in range(2):
            try:
                if not goal_handle.is_active:
                    return
                if goal_handle.is_cancel_requested:
                    goal_handle.canceled()
                else:
                    goal_handle.abort()
                return
            except RuntimeError:
                continue
