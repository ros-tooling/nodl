# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Generate an rclpy base-node module from a NoDL document."""

from __future__ import annotations

import argparse
import json
import keyword
import re
from pathlib import Path

import jinja2
import yaml

from nodl_schema import load_nodl

# ---------------------------------------------------------------------------
# Name utilities (identical to nodl_generator_cpp -- language-agnostic)
# ---------------------------------------------------------------------------


def _snake_to_pascal(name: str) -> str:
    return ''.join(part.capitalize() for part in name.split('_') if part)


def _topic_to_identifier(topic: str) -> str:
    return re.sub(r'[^a-zA-Z0-9]+', '_', topic.strip('/')).strip('_')


# ---------------------------------------------------------------------------
# ROS type utilities (Python flavour of cpp's _ros_type_to_cpp/_include)
# ---------------------------------------------------------------------------


def _split_ros_type(ros_type: str, default_kind: str) -> tuple[str, str, str]:
    """Split ``package[/kind]/TypeName`` -> (package, kind, TypeName).

    The middle namespace (msg/srv/action) is optional in NoDL; when omitted it
    is inferred from the usage context (default_kind).
    """
    parts = ros_type.split('/')
    if len(parts) == 3:
        if parts[1] != default_kind:
            raise ValueError(f'{ros_type!r} is a {parts[1]} type, expected {default_kind}')
        return parts[0], parts[1], parts[2]
    if len(parts) == 2:
        return parts[0], default_kind, parts[1]
    raise ValueError(f'malformed ROS type: {ros_type!r}')


def _ros_type_to_import(ros_type: str, default_kind: str) -> str:
    """Return a collision-safe module import for a ROS interface type."""
    package, kind, _ = _split_ros_type(ros_type, default_kind)
    return f'import {package}.{kind}'


def _ros_type_to_py(ros_type: str, default_kind: str) -> str:
    """Return the fully qualified Python symbol for a ROS interface type."""
    return '.'.join(_split_ros_type(ros_type, default_kind))


# ---------------------------------------------------------------------------
# QoS utilities (cpp's _qos_to_cpp -> an rclpy QoSProfile(...) expression)
# ---------------------------------------------------------------------------

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
    """Accept either a nodl_schema enum member or a bare string."""
    return value.value if hasattr(value, 'value') else value


def _qos_to_py(qos) -> str:
    """Render a nodl_schema QosProfile as a rclpy expression."""
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


# ---------------------------------------------------------------------------
# generate_parameter_library integration
# ---------------------------------------------------------------------------


def _write_params_yaml(yaml_path: Path, namespace: str, parameters: dict) -> None:
    """Write a generate_parameter_library-compatible YAML file.

    The NoDL parameters sub-schema is identical to the generate_parameter_library
    schema; the typed ParameterDefinition models are dumped back to plain dicts
    (by_alias so ``bounds<>`` etc. round-trip) and nested under the namespace.
    """
    plain = {name: json.loads(pdef.json(by_alias=True, exclude_none=True)) for name, pdef in parameters.items()}
    yaml_path.write_text(
        yaml.safe_dump({namespace: plain}, default_flow_style=False),
        encoding='utf-8',
    )


def _generate_params_module(params_py: Path, params_yaml: Path) -> None:
    """Call generate_parameter_library_py to produce the typed parameter module."""
    from generate_parameter_library_py.generate_python_module import run

    run(str(params_py), str(params_yaml), validation_module='')


# ---------------------------------------------------------------------------
# Template rendering context (over a typed nodl_schema.NodlDocument)
# ---------------------------------------------------------------------------


def _build_context(doc, target_name: str, lifecycle: bool) -> dict:
    class_name = _snake_to_pascal(target_name) + 'Base'
    imports: set[str] = set()

    if lifecycle:
        base_class = 'LifecycleNode'
        imports.add('from rclpy.lifecycle import LifecycleNode')
    else:
        base_class = 'Node'
        imports.add('from rclpy.node import Node')

    qos_profiles = []

    def endpoints(items, kind, member_prefix, callback_prefix=None, with_qos=False):
        result = []
        for endpoint in items or []:
            imports.add(_ros_type_to_import(endpoint.type, kind))
            ident = _topic_to_identifier(endpoint.name)
            item = {
                'name': endpoint.name,
                'py_type': _ros_type_to_py(endpoint.type, kind),
                'member_name': f'{member_prefix}{ident}',
            }
            if callback_prefix:
                item['callback_name'] = f'{callback_prefix}{ident}'
            if with_qos and endpoint.qos is not None:
                item['qos_py'] = _qos_to_py(endpoint.qos)
                qos_profiles.append(endpoint.qos)
            result.append(item)
        return result

    publishers = endpoints(doc.publishers, 'msg', 'pub_', with_qos=True)
    subscriptions = endpoints(doc.subscriptions, 'msg', 'sub_', 'on_', with_qos=True)
    service_servers = endpoints(doc.service_servers, 'srv', 'srv_', 'on_', with_qos=True)
    service_clients = endpoints(doc.service_clients, 'srv', 'cli_', with_qos=True)
    action_servers = endpoints(doc.action_servers, 'action', 'action_server_', 'execute_')
    action_clients = endpoints(doc.action_clients, 'action', 'action_client_')

    if action_servers or action_clients:
        imports.add('import rclpy.action')

    has_abstract = bool(subscriptions or service_servers or action_servers)
    if has_abstract:
        imports.add('import abc')
    if qos_profiles:
        imports.add('import rclpy.qos')
    if any(
        qos.deadline_ns is not None or qos.lifespan_ns is not None or qos.liveliness_lease_duration_ns is not None
        for qos in qos_profiles
    ):
        imports.add('from rclpy.duration import Duration')

    parameters = doc.parameters or {}

    return {
        'class_name': class_name,
        'node_name': target_name,
        'base_class': base_class,
        'publisher_factory': 'create_lifecycle_publisher' if lifecycle else 'create_publisher',
        'imports': sorted(imports, key=lambda value: (value.startswith('from '), value)),
        'has_params': bool(parameters),
        'params_module': f'{target_name}_params',
        'publishers': publishers,
        'subscriptions': subscriptions,
        'service_servers': service_servers,
        'service_clients': service_clients,
        'action_servers': action_servers,
        'action_clients': action_clients,
        'has_abstract': has_abstract,
    }


def generate(
    nodl_file: str | Path,
    output_dir: str | Path,
    target_name: str,
    templates_dir: str | Path,
    *,
    lifecycle: bool = False,
) -> Path:
    """Generate and return the path to ``<target_name>.py``."""
    if not target_name.isidentifier() or keyword.iskeyword(target_name):
        raise ValueError(f'target name must be a valid Python identifier: {target_name!r}')
    nodl_path = Path(nodl_file)
    if not nodl_path.exists():
        raise FileNotFoundError(f'NoDL file not found: {nodl_path}')
    doc = load_nodl(nodl_path.read_text(encoding='utf-8'))

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    context = _build_context(doc, target_name, lifecycle)

    if context['has_params']:
        params_yaml = output_dir / f'{target_name}_params.yaml'
        params_py = output_dir / f'{target_name}_params.py'
        _write_params_yaml(params_yaml, target_name, doc.parameters)
        _generate_params_module(params_py, params_yaml)

    environment = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(templates_dir)),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    text = environment.get_template('node.py.jinja2').render(**context)
    output = output_dir / f'{target_name}.py'
    output.write_text(text, encoding='utf-8')
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--nodl-file', required=True)
    parser.add_argument('--output-dir', required=True)
    parser.add_argument('--target-name', required=True)
    parser.add_argument('--templates-dir', required=True)
    parser.add_argument('--lifecycle', action='store_true')
    args = parser.parse_args()
    generate(
        args.nodl_file,
        args.output_dir,
        args.target_name,
        args.templates_dir,
        lifecycle=args.lifecycle,
    )


if __name__ == '__main__':
    main()
