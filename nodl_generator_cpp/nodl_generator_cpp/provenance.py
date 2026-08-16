# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Optional

from nodl_generator_cpp.models import CodegenCpp
from nodl_generator_cpp.schema import load as load_codegen_cpp
from nodl_schema.loader import DocumentTree, IncludedDocument
from nodl_schema.models import NodlDocument

# (kind, name): kind is the NodlDocument field name, name is the entity name
EntityKey = tuple[str, str]

# The NodlDocument fields that contain entities
_LIST_ENTITY_FIELDS = (
    'publishers',
    'subscriptions',
    'service_servers',
    'service_clients',
    'action_servers',
    'action_clients',
)


def _codegen_cpp(doc: NodlDocument) -> Optional[CodegenCpp]:
    """Load the ``codegen.cpp`` metadata from a document, or None."""
    if doc.codegen is None:
        return None
    return load_codegen_cpp(doc.codegen)


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
    owner: CodegenCpp,
    entity_map: dict[EntityKey, CodegenCpp],
) -> None:
    """Recursively collect all entities in ``node`` and its descendants, attributing them to ``owner``."""
    for key in _collect_entities(node.doc):
        entity_map[key] = owner
    for child in node.resolved_includes:
        _collect_subtree_entities(child, owner, entity_map)


def build_provenance_map(
    doc_tree: DocumentTree,
) -> tuple[list[CodegenCpp], dict[EntityKey, CodegenCpp]]:
    """Walk the include tree and build a provenance map.

    Returns a tuple of:

    - barriers: the list of ``CodegenCpp`` configs found at barrier
      level (the first ``codegen.cpp`` on each branch from the root).
      One entry per barrier encountered; duplicates are preserved so
      two sibling includes of the same class are still two barriers.
    - entity_map: maps every entity behind a barrier to the
      ``CodegenCpp`` that owns it.
    """
    barriers: list[CodegenCpp] = []
    entity_map: dict[EntityKey, CodegenCpp] = {}

    def walk(children: list[IncludedDocument]) -> None:
        for child in children:
            cpp = _codegen_cpp(child.doc)
            if cpp is not None:
                barriers.append(cpp)
                _collect_subtree_entities(child, cpp, entity_map)
            else:
                walk(child.resolved_includes)

    walk(doc_tree.resolved_includes)
    return barriers, entity_map
