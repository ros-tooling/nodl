# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Resolution of NoDL composition (base + fragments) into a LayeredDocument."""

from __future__ import annotations

import importlib.resources as ir
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from nodl_schema.models import (
    ActionEndpoint,
    NodlDocument,
    ParameterDefinition,
    ServiceEndpoint,
    TopicEndpoint,
)

_BUILTIN_BASES = frozenset(['node', 'lifecycle_node'])


def _load_builtin(base: str) -> NodlDocument:
    from nodl_schema.validator import load_nodl
    path = ir.files('nodl_schema') / 'schemas' / 'fragments' / f'{base}.nodl.yaml'
    return load_nodl(path.read_text(encoding='utf-8'))


def _load_ament_fragment(pkg: str, name: str) -> NodlDocument:
    try:
        from ament_index_python.packages import get_resource
    except ImportError as exc:
        raise ImportError('ament_index_python is required to resolve nodl:// URIs') from exc
    # Key format mirrors ament_nodl_register_fragment: pkg__name
    resource_key = f'{pkg}__{name}'
    try:
        content, _ = get_resource('nodl_fragments', resource_key)
    except KeyError:
        raise FileNotFoundError(
            f'NoDL fragment not found in ament index: {pkg}/{name} '
            f'(looked up as nodl_fragments/{resource_key})'
        )
    from nodl_schema.validator import load_nodl
    return load_nodl(content)


def _resolve_ref(ref: str, source_path: Optional[Path] = None) -> NodlDocument:
    if ref.startswith('nodl://'):
        rest = ref[len('nodl://'):]
        parts = rest.split('/', 1)
        if len(parts) != 2:
            raise ValueError(f'Invalid nodl:// URI: {ref!r} -- expected nodl://pkg/name')
        return _load_ament_fragment(parts[0], parts[1])
    if source_path is None:
        raise ValueError(f'Cannot resolve relative fragment ref {ref!r} without a source path')
    full_path = (source_path.parent / ref).resolve()
    if not full_path.exists():
        raise FileNotFoundError(f'Fragment file not found: {full_path}')
    from nodl_schema.validator import load_nodl
    return load_nodl(full_path.read_text(encoding='utf-8'))


@dataclass
class LayeredDocument:
    """A NoDL document with its resolved composition layers, keyed by label."""

    main: NodlDocument
    base: Optional[NodlDocument] = None
    base_name: Optional[str] = None
    fragments: Dict[str, NodlDocument] = field(default_factory=dict)

    def merged(self) -> NodlDocument:
        """Merge all layers into a flat NodlDocument.

        Layers applied in order: base -> named fragments (insertion order) -> main.
        Later layers win on duplicate names.
        """
        layers: List[NodlDocument] = []
        if self.base is not None:
            layers.append(self.base)
        layers.extend(self.fragments.values())
        layers.append(self.main)

        publishers: Dict[str, TopicEndpoint] = {}
        subscriptions: Dict[str, TopicEndpoint] = {}
        service_servers: Dict[str, ServiceEndpoint] = {}
        service_clients: Dict[str, ServiceEndpoint] = {}
        action_servers: Dict[str, ActionEndpoint] = {}
        action_clients: Dict[str, ActionEndpoint] = {}
        parameters: Dict[str, ParameterDefinition] = {}

        for doc in layers:
            for ep in (doc.publishers or []):
                publishers[ep.name] = ep
            for ep in (doc.subscriptions or []):
                subscriptions[ep.name] = ep
            for ep in (doc.service_servers or []):
                service_servers[ep.name] = ep
            for ep in (doc.service_clients or []):
                service_clients[ep.name] = ep
            for ep in (doc.action_servers or []):
                action_servers[ep.name] = ep
            for ep in (doc.action_clients or []):
                action_clients[ep.name] = ep
            for param_name, param in (doc.parameters or {}).items():
                parameters[param_name] = param

        return NodlDocument(
            nodl_version=self.main.nodl_version,
            parameters=parameters or None,
            publishers=list(publishers.values()) or None,
            subscriptions=list(subscriptions.values()) or None,
            service_servers=list(service_servers.values()) or None,
            service_clients=list(service_clients.values()) or None,
            action_servers=list(action_servers.values()) or None,
            action_clients=list(action_clients.values()) or None,
        )


def resolve(doc: NodlDocument, source_path: Optional[Path] = None) -> LayeredDocument:
    """Resolve a NodlDocument's base and fragments into a LayeredDocument.

    source_path: filesystem path to the NoDL file, used to resolve relative refs.
    Fragments are single-level only -- fragment files are not themselves resolved.
    """
    # doc.base is an enum on pydantic v2 and may be either enum or string on v1
    # depending on how the document was constructed. Normalize to the string value.
    base_name: Optional[str] = None
    if doc.base is not None:
        base_name = doc.base.value if hasattr(doc.base, 'value') else doc.base

    base_doc: Optional[NodlDocument] = None
    if base_name is not None:
        if base_name not in _BUILTIN_BASES:
            raise ValueError(f'Unknown base {base_name!r}. Must be one of: {sorted(_BUILTIN_BASES)}')
        base_doc = _load_builtin(base_name)

    fragment_docs: Dict[str, NodlDocument] = {}
    for frag_ref in (doc.fragments or []):
        label = frag_ref.name or frag_ref.ref
        fragment_docs[label] = _resolve_ref(frag_ref.ref, source_path=source_path)

    return LayeredDocument(
        main=doc,
        base=base_doc,
        base_name=base_name,
        fragments=fragment_docs,
    )
