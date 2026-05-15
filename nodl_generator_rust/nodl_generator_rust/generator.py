#!/usr/bin/env python3
"""Generate an rclrs node scaffolding module (.rs) from a NoDL YAML file."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Name utilities
# ---------------------------------------------------------------------------

def _to_snake(name: str) -> str:
    return re.sub(r'[^a-zA-Z0-9]+', '_', name.strip('/')).strip('_').lower()


def _to_pascal(snake: str) -> str:
    return ''.join(part.capitalize() for part in snake.split('_') if part)


# ---------------------------------------------------------------------------
# ROS type utilities
# ---------------------------------------------------------------------------

def _ros_type_to_rust(ros_type: str) -> str:
    """sensor_msgs/msg/LaserScan -> sensor_msgs::msg::LaserScan"""
    return ros_type.replace('/', '::')


def _ros_type_to_crate(ros_type: str) -> str:
    """sensor_msgs/msg/LaserScan -> sensor_msgs"""
    return ros_type.split('/')[0]


# ---------------------------------------------------------------------------
# NoDL type -> Rust type
# ---------------------------------------------------------------------------

_NODL_TO_RUST: dict[str, str] = {
    'bool': 'bool',
    'int': 'i64',
    'double': 'f64',
    'string': 'String',
    'byte_array': 'Vec<u8>',
    'bool_array': 'Vec<bool>',
    'int_array': 'Vec<i64>',
    'double_array': 'Vec<f64>',
    'string_array': 'Vec<String>',
}

_NODL_TO_RUST_DEFAULT: dict[str, str] = {
    'bool': 'false',
    'int': '0_i64',
    'double': '0.0_f64',
    'string': 'String::new()',
    'byte_array': 'vec![]',
    'bool_array': 'vec![]',
    'int_array': 'vec![]',
    'double_array': 'vec![]',
    'string_array': 'vec![]',
}


def _default_expr(nodl_type: str, default_value) -> str | None:
    if default_value is None:
        return None
    if nodl_type == 'string':
        return f'"{default_value}".to_string()'
    if nodl_type in ('byte_array', 'bool_array', 'int_array', 'double_array', 'string_array'):
        items = ', '.join(repr(v) for v in default_value)
        return f'vec![{items}]'
    if nodl_type == 'double':
        v = float(default_value)
        return f'{v}_f64' if '.' in str(v) else f'{v}.0_f64'
    if nodl_type == 'int':
        return f'{int(default_value)}_i64'
    return str(default_value).lower()  # bool


# ---------------------------------------------------------------------------
# QoS
# ---------------------------------------------------------------------------

def _qos_call(qos: dict | None) -> str:
    if not qos:
        return 'nodl_rclrs::qos::reliable(10)'
    history = qos.get('history', 'SYSTEM_DEFAULT')
    if history == 'KEEP_ALL':
        history_str = 'ALL'
    elif history == 'KEEP_LAST':
        depth = qos.get('depth', 10)
        history_str = str(depth)
    else:  # SYSTEM_DEFAULT
        history_str = 'SYSTEM_DEFAULT'
    reliability = qos.get('reliability', 'SYSTEM_DEFAULT')
    durability = qos.get('durability', 'VOLATILE') or 'VOLATILE'
    return (
        f'nodl_rclrs::profile_from_nodl("{history_str}", "{reliability}", "{durability}")'
    )


# ---------------------------------------------------------------------------
# Context builder
# ---------------------------------------------------------------------------

def _build_context(nodl_data: dict, target_name: str) -> dict:
    struct_name = _to_pascal(target_name)

    crates: set[str] = set()

    publishers = []
    for pub in (nodl_data.get('publishers') or []):
        crates.add(_ros_type_to_crate(pub['type']))
        topic_name = pub['name']
        ident = _to_snake(topic_name)
        publishers.append({
            'topic': topic_name,
            'rust_type': _ros_type_to_rust(pub['type']),
            'ident': ident,
            'qos_call': _qos_call(pub.get('qos')),
            'const_name': ident.upper(),
        })

    subscriptions = []
    for sub in (nodl_data.get('subscriptions') or []):
        crates.add(_ros_type_to_crate(sub['type']))
        topic_name = sub['name']
        ident = _to_snake(topic_name)
        subscriptions.append({
            'topic': topic_name,
            'rust_type': _ros_type_to_rust(sub['type']),
            'ident': ident,
            'qos_call': _qos_call(sub.get('qos')),
            'const_name': ident.upper(),
            'builder_method': f'on_{ident}',
        })

    service_servers = []
    for srv in (nodl_data.get('service_servers') or []):
        crates.add(_ros_type_to_crate(srv['type']))
        ident = _to_snake(srv['name'])
        service_servers.append({
            'name': srv['name'],
            'rust_type': _ros_type_to_rust(srv['type']),
            'ident': ident,
            'const_name': ident.upper(),
            'builder_method': f'on_{ident}',
        })

    service_clients = []
    for cli in (nodl_data.get('service_clients') or []):
        crates.add(_ros_type_to_crate(cli['type']))
        ident = _to_snake(cli['name'])
        service_clients.append({
            'name': cli['name'],
            'rust_type': _ros_type_to_rust(cli['type']),
            'ident': ident,
            'const_name': ident.upper(),
        })

    parameters = []
    for param_name, spec in (nodl_data.get('parameters') or {}).items():
        nodl_type = spec.get('type', 'string')
        rust_type = _NODL_TO_RUST.get(nodl_type, 'rclrs::ParameterValue')
        default_val = spec.get('default_value')
        default_expr = _default_expr(nodl_type, default_val)
        parameters.append({
            'name': param_name,
            'rust_type': rust_type,
            'has_default': default_expr is not None,
            'default_expr': default_expr,
            'read_only': bool(spec.get('read_only', False)),
        })

    return {
        'target_name': target_name,
        'struct_name': struct_name,
        'crates': sorted(crates),
        'publishers': publishers,
        'subscriptions': subscriptions,
        'service_servers': service_servers,
        'service_clients': service_clients,
        'parameters': parameters,
    }


# ---------------------------------------------------------------------------
# Render
# ---------------------------------------------------------------------------

def _render(templates_dir: Path, context: dict) -> str:
    try:
        import jinja2
    except ImportError:
        sys.exit('jinja2 is required')
    loader = jinja2.FileSystemLoader(str(templates_dir))
    env = jinja2.Environment(loader=loader, trim_blocks=True, lstrip_blocks=True)
    return env.get_template('node_nodl.rs.jinja2').render(**context)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--nodl-file', required=True)
    parser.add_argument('--output-dir', required=True)
    parser.add_argument('--target-name', required=True)
    parser.add_argument('--templates-dir', required=True)
    args = parser.parse_args()

    try:
        import yaml
    except ImportError:
        sys.exit('PyYAML is required')

    nodl_path = Path(args.nodl_file)
    if not nodl_path.exists():
        sys.exit(f'NoDL file not found: {nodl_path}')

    with nodl_path.open() as f:
        nodl_data = yaml.safe_load(f) or {}

    context = _build_context(nodl_data, args.target_name)
    rs_text = _render(Path(args.templates_dir), context)

    out = Path(args.output_dir) / f'{args.target_name}_nodl.rs'
    out.write_text(rs_text)


if __name__ == '__main__':
    main()
