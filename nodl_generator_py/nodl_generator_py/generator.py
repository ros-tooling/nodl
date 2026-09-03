# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Generate a standalone ``rclpy`` base module from a NoDL document."""

from __future__ import annotations

import importlib.resources
import keyword
import re

import jinja2

from nodl_schema.models import NodlDocument


def _snake_to_pascal(name: str) -> str:
    return ''.join(part.capitalize() for part in name.split('_') if part)


def _topic_to_identifier(topic: str) -> str:
    return re.sub(r'[^a-zA-Z0-9]+', '_', topic.strip('/')).strip('_')


def _split_ros_type(ros_type: str, expected_kind: str) -> tuple[str, str, str]:
    """Split ``package[/kind]/TypeName`` into its Python import components."""
    parts = ros_type.split('/')
    if len(parts) == 3:
        if parts[1] != expected_kind:
            raise ValueError(f'{ros_type!r} is a {parts[1]} type, expected {expected_kind}')
        return parts[0], parts[1], parts[2]
    if len(parts) == 2:
        return parts[0], expected_kind, parts[1]
    raise ValueError(f'malformed ROS type: {ros_type!r}')


def _ros_type_to_import(ros_type: str, expected_kind: str) -> str:
    package, kind, _ = _split_ros_type(ros_type, expected_kind)
    return f'import {package}.{kind}'


def _ros_type_to_py(ros_type: str, expected_kind: str) -> str:
    return '.'.join(_split_ros_type(ros_type, expected_kind))


_HISTORY = {
    'KEEP_LAST': 'rclpy.qos.HistoryPolicy.KEEP_LAST',
    'KEEP_ALL': 'rclpy.qos.HistoryPolicy.KEEP_ALL',
    'SYSTEM_DEFAULT': 'rclpy.qos.HistoryPolicy.SYSTEM_DEFAULT',
}
_RELIABILITY = {
    'RELIABLE': 'rclpy.qos.ReliabilityPolicy.RELIABLE',
    'BEST_EFFORT': 'rclpy.qos.ReliabilityPolicy.BEST_EFFORT',
    'SYSTEM_DEFAULT': 'rclpy.qos.ReliabilityPolicy.SYSTEM_DEFAULT',
    'BEST_AVAILABLE': 'rclpy.qos.ReliabilityPolicy.BEST_AVAILABLE',
}
_DURABILITY = {
    'TRANSIENT_LOCAL': 'rclpy.qos.DurabilityPolicy.TRANSIENT_LOCAL',
    'VOLATILE': 'rclpy.qos.DurabilityPolicy.VOLATILE',
    'SYSTEM_DEFAULT': 'rclpy.qos.DurabilityPolicy.SYSTEM_DEFAULT',
    'BEST_AVAILABLE': 'rclpy.qos.DurabilityPolicy.BEST_AVAILABLE',
}
_LIVELINESS = {
    'AUTOMATIC': 'rclpy.qos.LivelinessPolicy.AUTOMATIC',
    'MANUAL_BY_TOPIC': 'rclpy.qos.LivelinessPolicy.MANUAL_BY_TOPIC',
    'SYSTEM_DEFAULT': 'rclpy.qos.LivelinessPolicy.SYSTEM_DEFAULT',
    'BEST_AVAILABLE': 'rclpy.qos.LivelinessPolicy.BEST_AVAILABLE',
}


def _enum_value(value):
    return value.value if hasattr(value, 'value') else value


def _qos_to_py(qos) -> str:
    """Render a NoDL QoS profile as an ``rclpy.qos.QoSProfile`` expression."""
    args = [
        f'history={_HISTORY[_enum_value(qos.history)]}',
        f'depth={int(qos.depth) if qos.depth is not None else 10}',
        f'reliability={_RELIABILITY[_enum_value(qos.reliability)]}',
    ]
    for field, values in (('durability', _DURABILITY), ('liveliness', _LIVELINESS)):
        value = getattr(qos, field)
        if value is not None:
            args.append(f'{field}={values[_enum_value(value)]}')
    for field in ('deadline_ns', 'lifespan_ns', 'liveliness_lease_duration_ns'):
        value = getattr(qos, field)
        if value is not None:
            args.append(f'{field.removesuffix("_ns")}=Duration(nanoseconds={value})')
    arguments = '\n'.join(f'    {argument},' for argument in args)
    return f'rclpy.qos.QoSProfile(\n{arguments}\n)'


def _endpoints(items, imports: set[str], member_prefix: str, callback_prefix: str | None = None) -> list[dict]:
    result = []
    for endpoint in items or []:
        imports.add(_ros_type_to_import(endpoint.type, 'msg'))
        identifier = _topic_to_identifier(endpoint.name)
        item = {
            'name': endpoint.name,
            'py_type': _ros_type_to_py(endpoint.type, 'msg'),
            'member_name': f'{member_prefix}{identifier}',
            'qos_py': _qos_to_py(endpoint.qos),
        }
        if callback_prefix:
            item['callback_name'] = f'{callback_prefix}{identifier}'
        result.append(item)
    return result


def generate_python(doc: NodlDocument, target_name: str) -> str:
    """Render a Python module without writing to the filesystem."""
    if not target_name.isidentifier() or keyword.iskeyword(target_name):
        raise ValueError(f'target name must be a valid Python identifier: {target_name!r}')
    if doc.include:
        raise NotImplementedError('nodl_generator_py does not yet support include composition')

    imports = {'import rclpy.qos', 'from rclpy.node import Node'}
    publishers = _endpoints(doc.publishers, imports, 'pub_')
    subscriptions = _endpoints(doc.subscriptions, imports, 'sub_', 'on_')
    if subscriptions:
        imports.add('import abc')
    qos_profiles = [endpoint.qos for endpoint in (doc.publishers or []) + (doc.subscriptions or [])]
    if any(
        qos.deadline_ns is not None or qos.lifespan_ns is not None or qos.liveliness_lease_duration_ns is not None
        for qos in qos_profiles
    ):
        imports.add('from rclpy.duration import Duration')

    template = (
        importlib.resources.files('nodl_generator_py').joinpath('templates/node.py.jinja2').read_text(encoding='utf-8')
    )
    environment = jinja2.Environment(trim_blocks=True, lstrip_blocks=True)
    return environment.from_string(template).render(
        class_name=f'{_snake_to_pascal(target_name)}Base',
        node_name=target_name,
        imports=sorted(imports, key=lambda value: (value.startswith('from '), value)),
        publishers=publishers,
        subscriptions=subscriptions,
    )
