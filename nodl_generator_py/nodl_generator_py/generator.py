# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Generate a standalone ``rclpy`` base module from a NoDL document."""

from __future__ import annotations

import importlib.resources
import json
import keyword
from collections import deque
from dataclasses import dataclass
from pathlib import Path

import jinja2
import yaml

from nodl_generator_common.naming import to_member_name
from nodl_generator_common.parameters import nest_dotted_parameters
from nodl_generator_py.models import CodegenPython, Role
from nodl_generator_py.schema import load as load_codegen_python
from nodl_schema.composition import merge_documents
from nodl_schema.loader import DocumentTree, load_nodl_with_doc_tree
from nodl_schema.models import NodlDocument


class CodegenError(Exception):
    """Raised when Python code-generation configuration is invalid."""


@dataclass(frozen=True)
class PythonGeneration:
    """Generated Python content and its complete NoDL source set."""

    module: str
    parameters_yaml: str | None
    sources: list[Path]


_DEFAULT_BASE = CodegenPython(
    role=Role.BASE_CLASS,
    module='rclpy.node',
    **{'class': 'Node'},
)


def _snake_to_pascal(name: str) -> str:
    return ''.join(part.capitalize() for part in name.split('_') if part)


def _target_to_node_name(target_name: str) -> str:
    return target_name.removesuffix('_base')


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
        if value is not None and value > 0:
            args.append(f'{field.removesuffix("_ns")}=Duration(nanoseconds={value})')
    arguments = '\n'.join(f'    {argument},' for argument in args)
    return f'rclpy.qos.QoSProfile(\n{arguments}\n)'


def _endpoints(
    items,
    imports: set[str],
    kind: str,
    member_prefix: str,
    callback_prefix: str | None = None,
) -> list[dict]:
    result = []
    for endpoint in items or []:
        imports.add(_ros_type_to_import(endpoint.type, kind))
        identifier = to_member_name(endpoint.name)
        item = {
            'identifier': identifier,
            'name': endpoint.name,
            'py_type': _ros_type_to_py(endpoint.type, kind),
            'member_name': f'{member_prefix}{identifier}',
        }
        if callback_prefix:
            item['callback_name'] = f'{callback_prefix}{identifier}'
        if getattr(endpoint, 'qos', None) is not None:
            item['qos_py'] = _qos_to_py(endpoint.qos)
        result.append(item)
    return result


def generate_parameter_yaml(doc: NodlDocument, target_name: str) -> str | None:
    """Render the input consumed by ``generate_parameter_library_py``."""
    if not doc.parameters:
        return None
    parameters = nest_dotted_parameters({
        name: json.loads(definition.json(by_alias=True, exclude_none=True))
        for name, definition in doc.parameters.items()
    })
    return yaml.safe_dump({_target_to_node_name(target_name): parameters}, default_flow_style=False, sort_keys=False)


def _plan_tree(doc_tree: DocumentTree) -> tuple[list[CodegenPython], NodlDocument]:
    """Walk *doc_tree* and split it into base classes and the document the generator owns.

    An included document with ``codegen.python`` already has an implementation,
    so the walk does not descend into it.
    Its role decides what it contributes: ``BASE_CLASS`` its class, ``NO_GENERATE`` nothing.
    Every other document is owned, and the walk continues into its includes.
    The walk is breadth-first, matching the order of the fully merged document.
    """
    bases: list[CodegenPython] = []
    owned = [doc_tree.root_doc]
    queue = deque(doc_tree.resolved_includes)
    while queue:
        included = queue.popleft()
        config = load_codegen_python(included.doc.codegen) if included.doc.codegen else None
        if config is None:
            owned.append(included.doc)
            queue.extend(included.resolved_includes)
        elif config.role is Role.BASE_CLASS:
            bases.append(config)
    return bases, merge_documents(owned)


def _find_base_class_config(base_classes: list[CodegenPython]) -> CodegenPython:
    """Select the one visible provider, or the compatible implicit Node base."""
    if not base_classes:
        return _DEFAULT_BASE
    if len(base_classes) > 1:
        classes = ', '.join(base.class_ for base in base_classes if base.class_ is not None)
        raise CodegenError(
            f'Multiple conflicting Python base class providers found: {classes}. '
            'A generated node can only inherit from one base class.'
        )
    base = base_classes[0]
    assert base.module is not None
    assert base.class_ is not None
    assert base.publisher_method is not None
    return base


def _render_python(
    doc: NodlDocument,
    target_name: str,
    base: CodegenPython = _DEFAULT_BASE,
) -> str:
    """Render an already resolved document of only the entities to generate."""
    if doc.include:
        raise NotImplementedError('_render_python requires a resolved, flat NoDL document')
    if not target_name.isidentifier() or keyword.iskeyword(target_name):
        raise ValueError(f'target name must be a valid Python identifier: {target_name!r}')

    imports = {f'from {base.module} import {base.class_}'}
    publishers = _endpoints(doc.publishers, imports, 'msg', 'pub_')
    subscriptions = _endpoints(doc.subscriptions, imports, 'msg', 'sub_', 'on_')
    service_servers = _endpoints(doc.service_servers, imports, 'srv', 'srv_', 'on_')
    service_clients = _endpoints(doc.service_clients, imports, 'srv', 'cli_')
    action_servers = _endpoints(doc.action_servers, imports, 'action', 'action_srv_', 'execute_')
    action_clients = _endpoints(doc.action_clients, imports, 'action', 'action_cli_')
    if subscriptions or service_servers or action_servers:
        imports.add('import abc')
    if action_servers or action_clients:
        imports.add('import rclpy.action')
    qos_endpoints = (
        (doc.publishers or []) + (doc.subscriptions or []) + (doc.service_servers or []) + (doc.service_clients or [])
    )
    qos_profiles = [endpoint.qos for endpoint in qos_endpoints if endpoint.qos is not None]
    if qos_profiles:
        imports.add('import rclpy.qos')
    if any(
        (qos.deadline_ns or 0) > 0 or (qos.lifespan_ns or 0) > 0 or (qos.liveliness_lease_duration_ns or 0) > 0
        for qos in qos_profiles
    ):
        imports.add('from rclpy.duration import Duration')

    template = (
        importlib.resources.files('nodl_generator_py').joinpath('templates/node.py.jinja2').read_text(encoding='utf-8')
    )
    environment = jinja2.Environment(trim_blocks=True, lstrip_blocks=True)
    return environment.from_string(template).render(
        class_name=_snake_to_pascal(target_name),
        base_class=base.class_,
        publisher_method=base.publisher_method,
        node_name=_target_to_node_name(target_name),
        imports=sorted(imports, key=lambda value: (value.startswith('from '), value)),
        params_module=f'{target_name}_parameters' if doc.parameters else None,
        publishers=publishers,
        subscriptions=subscriptions,
        service_servers=service_servers,
        service_clients=service_clients,
        action_servers=action_servers,
        action_clients=action_clients,
    )


def generate_python(source: Path, target_name: str) -> PythonGeneration:
    """Resolve includes and generate Python content from a NoDL source file."""
    # Loading still merges the whole tree, so name collisions anywhere in it are reported.
    _, doc_tree = load_nodl_with_doc_tree(source)
    bases, doc = _plan_tree(doc_tree)
    base = _find_base_class_config(bases)
    return PythonGeneration(
        module=_render_python(doc, target_name, base),
        parameters_yaml=generate_parameter_yaml(doc, target_name),
        sources=[source.resolve(), *(path.resolve() for path in doc_tree.included_paths())],
    )


def format_cmake_deps(target_name: str, sources: list[Path]) -> str:
    """Render the transitive NoDL source list consumed by CMake."""
    lines = [
        '# Auto-generated by nodl_generator_py --cmake-deps',
        '# Do not edit.',
        f'set({target_name}_NODL_SOURCES',
        *(f'  {source}' for source in sources),
        ')',
    ]
    return '\n'.join(lines) + '\n'
