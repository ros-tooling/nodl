# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from dataclasses import dataclass

from nodl_generator_cpp.ros_to_cpp import (
    qos_to_cpp,
    ros_type_to_cpp,
    ros_type_to_header,
    to_class_name,
    to_member_name,
)
from nodl_schema.models import ActionEndpoint, ServiceEndpoint, TopicEndpoint


@dataclass
class GeneratedFile:
    """A generated file ready to be written to disk."""

    filename: str
    content: str


def _build_template_context(
    target_name: str,
    base_class: str,
    base_header: str,
    publishers: list[TopicEndpoint],
    subscriptions: list[TopicEndpoint],
    service_servers: list[ServiceEndpoint],
    service_clients: list[ServiceEndpoint],
    action_servers: list[ActionEndpoint],
    action_clients: list[ActionEndpoint],
) -> dict:
    """Build the flat context dict consumed by the Jinja2 templates.

    All ROS-domain values are pre-converted to C++ strings so the
    templates contain no conversion logic.
    """
    has_actions = bool(action_servers or action_clients)

    # -- Collect includes (sorted, deduped) --
    headers: set[str] = {base_header}
    if has_actions:
        headers.add('rclcpp_action/rclcpp_action.hpp')

    type_sources: list[str] = (
        [e.type for e in publishers]
        + [e.type for e in subscriptions]
        + [e.type for e in service_servers]
        + [e.type for e in service_clients]
        + [e.type for e in action_servers]
        + [e.type for e in action_clients]
    )
    for ros_type in type_sources:
        headers.add(ros_type_to_header(ros_type))

    # -- Pre-process entity lists --
    pub_ctx = [
        {
            'name': e.name,
            'cpp_type': ros_type_to_cpp(e.type),
            'member': f'pub_{to_member_name(e.name)}_',
            'qos': qos_to_cpp(e.qos),
        }
        for e in publishers
    ]

    sub_ctx = [
        {
            'name': e.name,
            'cpp_type': ros_type_to_cpp(e.type),
            'member': f'sub_{to_member_name(e.name)}_',
            'callback': f'on_{to_member_name(e.name)}',
            'qos': qos_to_cpp(e.qos),
        }
        for e in subscriptions
    ]

    srv_server_ctx = [
        {
            'name': e.name,
            'cpp_type': ros_type_to_cpp(e.type),
            'member': f'srv_{to_member_name(e.name)}_',
            'callback': f'on_{to_member_name(e.name)}',
        }
        for e in service_servers
    ]

    srv_client_ctx = [
        {
            'name': e.name,
            'cpp_type': ros_type_to_cpp(e.type),
            'member': f'cli_{to_member_name(e.name)}_',
        }
        for e in service_clients
    ]

    action_server_ctx = [
        {
            'name': e.name,
            'cpp_type': ros_type_to_cpp(e.type),
            'member': f'action_srv_{to_member_name(e.name)}_',
            'callback_prefix': f'on_{to_member_name(e.name)}',
        }
        for e in action_servers
    ]

    action_client_ctx = [
        {
            'name': e.name,
            'cpp_type': ros_type_to_cpp(e.type),
            'member': f'action_cli_{to_member_name(e.name)}_',
        }
        for e in action_clients
    ]

    return {
        'target_name': target_name,
        'class_name': to_class_name(target_name),
        'base_class': base_class,
        'base_header': base_header,
        'includes': sorted(headers),
        'publishers': pub_ctx,
        'subscriptions': sub_ctx,
        'service_servers': srv_server_ctx,
        'service_clients': srv_client_ctx,
        'action_servers': action_server_ctx,
        'action_clients': action_client_ctx,
    }


def render_templates(
    target_name: str,
    base_class: str,
    base_header: str,
    publishers: list[TopicEndpoint],
    subscriptions: list[TopicEndpoint],
    service_servers: list[ServiceEndpoint],
    service_clients: list[ServiceEndpoint],
    action_servers: list[ActionEndpoint],
    action_clients: list[ActionEndpoint],
) -> list[GeneratedFile]:
    """Render C++ header and source files from pre-filtered entities.

    Builds a template context, renders the Jinja2 templates, and returns
    the generated files.
    """
    _ = _build_template_context(
        target_name,
        base_class,
        base_header,
        publishers,
        subscriptions,
        service_servers,
        service_clients,
        action_servers,
        action_clients,
    )

    # TODO: Jinja2 template loading and rendering
    return []
