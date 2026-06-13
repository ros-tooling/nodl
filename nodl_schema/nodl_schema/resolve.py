# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Resolution of a node definition (base + mixins + main) into a ResolvedNode."""

from __future__ import annotations

import importlib.resources as ir
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from nodl_schema.models import (
    ActionEndpoint,
    Interface,
    Node,
    ParameterDefinition,
    ServiceEndpoint,
    TopicEndpoint,
)


def _load_builtin(base: str) -> Interface:
    from nodl_schema.validator import load_interface

    path = ir.files('nodl_schema') / 'schemas' / 'bases' / f'{base}.nodl.yaml'
    return load_interface(path.read_text(encoding='utf-8'))


def _load_ament_interface(pkg: str, name: str) -> Interface:
    try:
        from ament_index_python.packages import get_resource
    except ImportError as exc:
        raise ImportError('ament_index_python is required to resolve nodl:// URIs') from exc
    # Key format mirrors ament_nodl_register_interface: pkg__name
    resource_key = f'{pkg}__{name}'
    try:
        content, _ = get_resource('nodl_interfaces', resource_key)
    except KeyError:
        raise FileNotFoundError(
            f'NoDL interface definition not found in ament index: {pkg}/{name} '
            f'(looked up as nodl_interfaces/{resource_key})'
        )
    from nodl_schema.validator import load_interface

    return load_interface(content)


def _resolve_ref(ref: str, source_path: Optional[Path] = None) -> Interface:
    """Resolve a mixin reference string to an interface definition."""
    if ref.startswith('nodl://'):
        rest = ref[len('nodl://') :]
        parts = rest.split('/', 1)
        if len(parts) != 2:
            raise ValueError(f'Invalid nodl:// URI: {ref!r} -- expected nodl://pkg/name')
        return _load_ament_interface(parts[0], parts[1])
    if source_path is None:
        raise ValueError(f'Cannot resolve relative mixin ref {ref!r} without a source path')
    full_path = (source_path.parent / ref).resolve()
    if not full_path.exists():
        raise FileNotFoundError(f'Mixin interface definition not found: {full_path}')
    from nodl_schema.validator import load_interface

    return load_interface(full_path.read_text(encoding='utf-8'))


@dataclass
class ResolvedNode:
    """A node definition with its resolved composition layers."""

    main: Interface
    base: Optional[Interface] = None
    base_name: Optional[str] = None
    mixins: List[Interface] = field(default_factory=list)

    def merged(self) -> Interface:
        """Merge all layers into a flat interface definition.

        Layers applied in order: base -> mixins (declared order) -> main.
        Later layers win on duplicate names.
        """
        layers: List[Interface] = []
        if self.base is not None:
            layers.append(self.base)
        layers.extend(self.mixins)
        layers.append(self.main)

        publishers: Dict[str, TopicEndpoint] = {}
        subscriptions: Dict[str, TopicEndpoint] = {}
        service_servers: Dict[str, ServiceEndpoint] = {}
        service_clients: Dict[str, ServiceEndpoint] = {}
        action_servers: Dict[str, ActionEndpoint] = {}
        action_clients: Dict[str, ActionEndpoint] = {}
        parameters: Dict[str, ParameterDefinition] = {}

        for doc in layers:
            for ep in doc.publishers or []:
                publishers[ep.name] = ep
            for ep in doc.subscriptions or []:
                subscriptions[ep.name] = ep
            for ep in doc.service_servers or []:
                service_servers[ep.name] = ep
            for ep in doc.service_clients or []:
                service_clients[ep.name] = ep
            for ep in doc.action_servers or []:
                action_servers[ep.name] = ep
            for ep in doc.action_clients or []:
                action_clients[ep.name] = ep
            for param_name, param in (doc.parameters or {}).items():
                parameters[param_name] = param

        return Interface(
            nodl_version=self.main.nodl_version,
            parameters=parameters or None,
            publishers=list(publishers.values()) or None,
            subscriptions=list(subscriptions.values()) or None,
            service_servers=list(service_servers.values()) or None,
            service_clients=list(service_clients.values()) or None,
            action_servers=list(action_servers.values()) or None,
            action_clients=list(action_clients.values()) or None,
        )


def resolve(node: Node, source_path: Optional[Path] = None) -> ResolvedNode:
    """Resolve a node definition's base and mixins into a ResolvedNode.

    source_path: filesystem path to the node file, used to resolve relative
    mixin refs. Mixins are single-level only -- referenced interface definitions
    are not themselves resolved (an interface definition cannot declare
    base/mixins).
    """
    # node.base is an enum on pydantic v2 and may be enum or str on v1.
    base_name: Optional[str] = None
    if node.base is not None:
        base_name = node.base.value if hasattr(node.base, 'value') else node.base

    base_doc = _load_builtin(base_name) if base_name is not None else None

    mixin_docs: List[Interface] = []
    for mixin in node.mixins or []:
        if isinstance(mixin, Interface):
            mixin_docs.append(mixin)
        else:
            mixin_docs.append(_resolve_ref(mixin, source_path=source_path))

    return ResolvedNode(main=node.main, base=base_doc, base_name=base_name, mixins=mixin_docs)
