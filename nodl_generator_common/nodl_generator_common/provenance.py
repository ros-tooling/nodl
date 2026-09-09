# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Language-agnostic include-tree provenance.

The barrier walk DFS-walks the resolved include tree; the first document on each
branch that carries language codegen metadata is a *barrier* that owns every
entity in its whole subtree. Generators filter out anything behind a barrier
(already implemented by a base or dependency) and scaffold the rest.

The walk is parameterised by an ``extract_config`` callback that returns a
document's parsed language config, or ``None`` if it carries none -- this
predicate is what defines a barrier, keeping the core generic over any target
language.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional, TypeVar

from nodl_schema.loader import DocumentTree, IncludedDocument
from nodl_schema.models import (
    ActionEndpoint,
    NodlDocument,
    ParameterDefinition,
    ServiceEndpoint,
    TopicEndpoint,
)

T = TypeVar('T')

# (kind, name): kind is the NodlDocument field name, name is the entity name.
EntityKey = tuple[str, str]

# The NodlDocument fields that contain lists of named endpoints.
_LIST_ENTITY_FIELDS = (
    'publishers',
    'subscriptions',
    'service_servers',
    'service_clients',
    'action_servers',
    'action_clients',
)


def _collect_entities(doc: NodlDocument) -> set[EntityKey]:
    """Return every entity key declared directly in ``doc`` (not its includes)."""
    keys: set[EntityKey] = set()
    for field in _LIST_ENTITY_FIELDS:
        for endpoint in getattr(doc, field) or []:
            keys.add((field, endpoint.name))
    for param_name in doc.parameters or {}:
        keys.add(('parameters', param_name))
    return keys


def _collect_subtree_entities(
    node: IncludedDocument,
    owner: T,
    entity_map: dict[EntityKey, T],
) -> None:
    """Recursively collect all entities in ``node`` and its descendants, attributing them to ``owner``."""
    for key in _collect_entities(node.doc):
        entity_map[key] = owner
    for child in node.resolved_includes:
        _collect_subtree_entities(child, owner, entity_map)


def build_provenance_map(
    doc_tree: DocumentTree,
    extract_config: Callable[[NodlDocument], Optional[T]],
) -> tuple[list[T], dict[EntityKey, T]]:
    """Walk the include tree and build a provenance map.

    ``extract_config`` returns the parsed language config for a document, or
    ``None`` if it carries none. A document for which it returns non-``None`` is
    a *barrier* that owns every entity in its whole subtree.

    Returns a tuple of:

    - barriers: the config found at each barrier (the first non-``None``
      ``extract_config`` on each branch from the root). One entry per barrier
      encountered; duplicates are preserved so two sibling includes of the same
      class are still two barriers.
    - entity_map: maps every entity behind a barrier to the config that owns it.
    """
    barriers: list[T] = []
    entity_map: dict[EntityKey, T] = {}

    def walk(children: list[IncludedDocument]) -> None:
        for child in children:
            config = extract_config(child.doc)
            if config is not None:
                barriers.append(config)
                _collect_subtree_entities(child, config, entity_map)
            else:
                walk(child.resolved_includes)

    walk(doc_tree.resolved_includes)
    return barriers, entity_map


@dataclass(frozen=True)
class FilteredEntities:
    """The merged-document entities that are *not* behind a provenance barrier.

    Everything a generator must scaffold itself: the six endpoint lists (in
    ``NodlDocument`` field order) plus the surviving parameters.
    """

    publishers: list[TopicEndpoint]
    subscriptions: list[TopicEndpoint]
    service_servers: list[ServiceEndpoint]
    service_clients: list[ServiceEndpoint]
    action_servers: list[ActionEndpoint]
    action_clients: list[ActionEndpoint]
    parameters: dict[str, ParameterDefinition]


def filter_provided_entities(
    merged_doc: NodlDocument,
    provenance_map: dict[EntityKey, T],
) -> FilteredEntities:
    """Keep only the merged-document entities not behind a barrier.

    Given the merged document and a provenance map keyed by :data:`EntityKey`,
    returns the entities the generator must scaffold itself -- everything not
    already provided by a base or dependency.
    """

    def _keep(field: str, items: list | None) -> list:
        return [e for e in (items or []) if (field, e.name) not in provenance_map]

    parameters = {
        name: param
        for name, param in (merged_doc.parameters or {}).items()
        if ('parameters', name) not in provenance_map
    }

    return FilteredEntities(
        publishers=_keep('publishers', merged_doc.publishers),
        subscriptions=_keep('subscriptions', merged_doc.subscriptions),
        service_servers=_keep('service_servers', merged_doc.service_servers),
        service_clients=_keep('service_clients', merged_doc.service_clients),
        action_servers=_keep('action_servers', merged_doc.action_servers),
        action_clients=_keep('action_clients', merged_doc.action_clients),
        parameters=parameters,
    )
