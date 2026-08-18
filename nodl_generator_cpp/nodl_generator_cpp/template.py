# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
import jinja2

from nodl_generator_cpp.generated_file import GeneratedFile
from nodl_generator_cpp.ros_to_cpp import (
    qos_to_cpp,
    ros_type_to_cpp,
    ros_type_to_header,
    to_class_name,
    to_member_name,
)
from nodl_schema.models import ActionEndpoint, ServiceEndpoint, TopicEndpoint

# ---------------------------------------------------------------------------
# Jinja2 environment (lazy singleton)
# ---------------------------------------------------------------------------

_env_cache: jinja2.Environment | None = None


def _get_env() -> jinja2.Environment:
    global _env_cache
    if _env_cache is None:
        _env_cache = jinja2.Environment(
            loader=jinja2.PackageLoader('nodl_generator_cpp', 'templates'),
            trim_blocks=True,
            lstrip_blocks=True,
            keep_trailing_newline=True,
            undefined=jinja2.StrictUndefined,
        )
    return _env_cache


# ---------------------------------------------------------------------------
# Context builder
# ---------------------------------------------------------------------------


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
    has_parameters: bool = False,
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

    return {
        'target_name': target_name,
        'class_name': to_class_name(target_name),
        'base_class': base_class,
        'includes': sorted(headers),
        'publishers': [
            {
                'name': e.name,
                'cpp_type': ros_type_to_cpp(e.type),
                'member': f'pub_{to_member_name(e.name)}_',
                'qos': qos_to_cpp(e.qos),
            }
            for e in publishers
        ],
        'subscriptions': [
            {
                'name': e.name,
                'cpp_type': ros_type_to_cpp(e.type),
                'member': f'sub_{to_member_name(e.name)}_',
                'callback': f'on_{to_member_name(e.name)}',
                'qos': qos_to_cpp(e.qos),
            }
            for e in subscriptions
        ],
        'service_servers': [
            {
                'name': e.name,
                'cpp_type': ros_type_to_cpp(e.type),
                'member': f'srv_{to_member_name(e.name)}_',
                'callback': f'on_{to_member_name(e.name)}',
            }
            for e in service_servers
        ],
        'service_clients': [
            {
                'name': e.name,
                'cpp_type': ros_type_to_cpp(e.type),
                'member': f'cli_{to_member_name(e.name)}_',
            }
            for e in service_clients
        ],
        'action_servers': [
            {
                'name': e.name,
                'cpp_type': ros_type_to_cpp(e.type),
                'member': f'action_srv_{to_member_name(e.name)}_',
                'callback_prefix': f'on_{to_member_name(e.name)}',
            }
            for e in action_servers
        ],
        'action_clients': [
            {
                'name': e.name,
                'cpp_type': ros_type_to_cpp(e.type),
                'member': f'action_cli_{to_member_name(e.name)}_',
            }
            for e in action_clients
        ],
        'has_parameters': has_parameters,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


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
    has_parameters: bool = False,
) -> list[GeneratedFile]:
    """Render C++ header and source files from pre-filtered entities.

    Builds a template context, renders the Jinja2 templates, and returns
    the generated files.
    """
    ctx = _build_template_context(
        target_name,
        base_class,
        base_header,
        publishers,
        subscriptions,
        service_servers,
        service_clients,
        action_servers,
        action_clients,
        has_parameters,
    )

    env = _get_env()
    hpp = env.get_template('node.hpp.j2').render(ctx)
    cpp = env.get_template('node.cpp.j2').render(ctx)

    return [
        GeneratedFile(filename=f'{target_name}.hpp', content=hpp),
        GeneratedFile(filename=f'{target_name}.cpp', content=cpp),
    ]
