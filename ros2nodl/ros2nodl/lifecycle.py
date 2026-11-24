# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Bring a running lifecycle node to the active state through its lifecycle services.

A lifecycle node that creates its endpoints on activation shows none of them until it is active.
:func:`activate_node` brings such a node to active, and :func:`declares_lifecycle` tells from a document whether a node needs it.
"""

from __future__ import annotations

import os
import time
from collections.abc import Callable
from typing import NamedTuple

from lifecycle_msgs.msg import State, Transition

from nodl_schema.models import NodlDocument

_CHANGE_STATE_NAME = '~/change_state'
_CHANGE_STATE_TYPES = {'lifecycle_msgs/srv/ChangeState', 'lifecycle_msgs/ChangeState'}


class LifecycleError(RuntimeError):
    """A node did not reach the active state."""


class NodeState(NamedTuple):
    """The state of a lifecycle node, as ``~/get_state`` reports it."""

    id: int
    label: str


def declares_lifecycle(doc: NodlDocument) -> bool:
    """Return whether ``doc`` declares the ``~/change_state`` service of ``lifecycle_msgs/srv/ChangeState``."""
    return any(
        _CHANGE_STATE_NAME == server.name and server.type in _CHANGE_STATE_TYPES for server in doc.service_servers or []
    )


def activate_with(
    node_fqn: str,
    *,
    get_state: Callable[[], NodeState],
    change_state: Callable[[int], bool],
) -> None:
    """Bring a node to active with the two lifecycle services, given as functions.

    It configures the node only if it is unconfigured, activates it if it is inactive, and does nothing if it is active.
    ``change_state`` takes a ``lifecycle_msgs/msg/Transition`` id and returns whether the node accepted the transition.

    :raises LifecycleError: if the node is in another state, or a transition fails, naming the state the node reached.
    """
    state = get_state()
    if State.PRIMARY_STATE_UNCONFIGURED == state.id:
        _transition(
            node_fqn,
            'configure',
            Transition.TRANSITION_CONFIGURE,
            State.PRIMARY_STATE_INACTIVE,
            get_state,
            change_state,
        )
        state = get_state()
    if State.PRIMARY_STATE_INACTIVE == state.id:
        _transition(
            node_fqn, 'activate', Transition.TRANSITION_ACTIVATE, State.PRIMARY_STATE_ACTIVE, get_state, change_state
        )
        return
    if State.PRIMARY_STATE_ACTIVE != state.id:
        raise LifecycleError(
            f'cannot activate {node_fqn}: it is {state.label}, and only an unconfigured or inactive node can be'
        )


def _transition(
    node_fqn: str,
    name: str,
    transition_id: int,
    target: int,
    get_state: Callable[[], NodeState],
    change_state: Callable[[int], bool],
) -> None:
    accepted = change_state(transition_id)
    reached = get_state()
    if not accepted or target != reached.id:
        raise LifecycleError(
            f'cannot activate {node_fqn}: the {name} transition failed, and the node is {reached.label}'
        )


def activate_node(node_fqn: str, *, timeout_sec: float = 15.0) -> None:
    """Bring the lifecycle node ``node_fqn`` to active within ``timeout_sec``, as :func:`activate_with` does.

    It calls ``<node_fqn>/get_state`` and ``<node_fqn>/change_state``, so the node must serve them.

    :raises LifecycleError: if the node does not serve the services in time, a call times out, or the node does not reach active.
        The message names the node and the state it last reported.
    """
    import rclpy
    from lifecycle_msgs.srv import ChangeState, GetState
    from rclpy.utilities import ok

    deadline = time.monotonic() + timeout_sec
    last_label = 'none'

    def remaining() -> float:
        return max(0.0, deadline - time.monotonic())

    owns_context = not ok()
    if owns_context:
        rclpy.init()
    try:
        node = rclpy.create_node(f'_ros2nodl_activate_{os.getpid()}', start_parameter_services=False)
        try:
            get_client = node.create_client(GetState, f'{node_fqn}/get_state')
            change_client = node.create_client(ChangeState, f'{node_fqn}/change_state')

            def call(client, request):
                future = client.call_async(request)
                rclpy.spin_until_future_complete(node, future, timeout_sec=remaining())
                if not future.done():
                    future.cancel()
                    raise LifecycleError(
                        f'cannot activate {node_fqn}: no answer within {timeout_sec} s, the last state it reported was {last_label}'
                    )
                result = future.result()
                if result is None:
                    raise LifecycleError(f'cannot activate {node_fqn}: {client.srv_name} returned no response')
                return result

            def get_state() -> NodeState:
                nonlocal last_label
                current = call(get_client, GetState.Request()).current_state
                last_label = current.label
                return NodeState(current.id, current.label)

            def change_state(transition_id: int) -> bool:
                request = ChangeState.Request()
                request.transition.id = transition_id
                return call(change_client, request).success

            for client in (get_client, change_client):
                if not client.wait_for_service(timeout_sec=remaining()):
                    raise LifecycleError(
                        f'cannot activate {node_fqn}: {client.srv_name} was not available within {timeout_sec} s'
                    )
            activate_with(node_fqn, get_state=get_state, change_state=change_state)
        finally:
            node.destroy_node()
    finally:
        if owns_context:
            rclpy.shutdown()
