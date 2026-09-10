# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Knowledge of the endpoints and parameters that the ROS middleware creates.

Every rcl node exposes framework-created interfaces (``/rosout``, ``/parameter_events``,
the parameter services, ``use_sim_time``) that are not part of a node's declared contract.
This module is the single source of truth for identifying them, usable on its own to
filter any :class:`~nodl_schema.models.NodlDocument` regardless of where it came from.
"""

from __future__ import annotations

from nodl_schema.models import NodlDocument

# Framework-created endpoints are matched by both name tail and type so user
# endpoints with a colliding name survive.
_HIDDEN_PUBLISHERS = {
    ('rosout', 'rcl_interfaces/msg/Log'),
    ('parameter_events', 'rcl_interfaces/msg/ParameterEvent'),
}
_HIDDEN_SUBSCRIPTIONS = {
    ('parameter_events', 'rcl_interfaces/msg/ParameterEvent'),
}
_HIDDEN_SERVICES = {
    ('describe_parameters', 'rcl_interfaces/srv/DescribeParameters'),
    ('get_parameter_types', 'rcl_interfaces/srv/GetParameterTypes'),
    ('get_parameters', 'rcl_interfaces/srv/GetParameters'),
    ('list_parameters', 'rcl_interfaces/srv/ListParameters'),
    ('set_parameters', 'rcl_interfaces/srv/SetParameters'),
    ('set_parameters_atomically', 'rcl_interfaces/srv/SetParametersAtomically'),
    ('get_type_description', 'type_description_interfaces/srv/GetTypeDescription'),
}
_HIDDEN_PARAMETERS = {'use_sim_time', 'start_type_description_service'}


def name_tail(name: str) -> str:
    return name.rsplit('/', 1)[-1]


def is_hidden_publisher(name: str, type: str) -> bool:
    return (name_tail(name), type) in _HIDDEN_PUBLISHERS


def is_hidden_subscription(name: str, type: str) -> bool:
    return (name_tail(name), type) in _HIDDEN_SUBSCRIPTIONS


def is_hidden_service(name: str, type: str) -> bool:
    return (name_tail(name), type) in _HIDDEN_SERVICES


def is_hidden_parameter(name: str) -> bool:
    return name in _HIDDEN_PARAMETERS or name.startswith('qos_overrides.')


_ENDPOINT_PREDICATES = {
    'publishers': is_hidden_publisher,
    'subscriptions': is_hidden_subscription,
    'service_servers': is_hidden_service,
    'service_clients': is_hidden_service,
}


def strip_infrastructure(doc: NodlDocument) -> NodlDocument:
    """Return a copy of ``doc`` with framework-created endpoints and parameters removed.

    Symmetric with describe's ``keep_hidden=False``:
    a no-op on an already-stripped document,
    and on a spec that includes ``nodl://rclcpp/node`` it removes exactly the
    endpoints and parameters that live introspection hides.
    """
    updates: dict = {}
    for field, hidden in _ENDPOINT_PREDICATES.items():
        endpoints = getattr(doc, field, None)
        if endpoints:
            updates[field] = [ep for ep in endpoints if not hidden(ep.name, ep.type)] or None
    if doc.parameters:
        updates['parameters'] = {
            name: definition for name, definition in doc.parameters.items() if not is_hidden_parameter(name)
        } or None
    return doc.copy(update=updates)
