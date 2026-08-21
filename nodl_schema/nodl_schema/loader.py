# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
import json
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import IO, TypeAlias, Union

import yaml

from nodl_schema.composition import ResolutionError, merge_documents, resolve
from nodl_schema.models import NodlDocument
from nodl_schema.validation import validate


@dataclass
class IncludedDocument:
    ref: str
    doc: NodlDocument
    resolved_includes: list['IncludedDocument']


@dataclass
class DocumentTree:
    # NOTE(alistair) this is a special case of a IncludedDocument because we dont have the root ref
    root_doc: NodlDocument
    resolved_includes: list[IncludedDocument]

    def flatten(self) -> list[NodlDocument]:
        result = [self.root_doc]
        queue = deque(self.resolved_includes)
        while queue:
            included_doc = queue.popleft()
            result.append(included_doc.doc)
            queue.extend(included_doc.resolved_includes)
        return result


Ref: TypeAlias = str
IncludeChain: TypeAlias = list[str]


def resolve_document(doc: NodlDocument, origin: Path | None = None) -> DocumentTree:
    # DFS traversal of the includes, detecting non-tree double-inclusions/cycles

    visited: dict[Path, IncludeChain] = {}

    def _resolve_ref(ref: Ref, *, chain: IncludeChain, origin: Path | None) -> IncludedDocument:
        current_chain = chain + [ref]
        resolved_path = resolve(ref, origin)

        if resolved_path in visited:
            other_chain = visited[resolved_path]
            chain_a = ' > '.join(current_chain)
            chain_b = ' > '.join(other_chain)
            raise ResolutionError(f'Double-inclusion detected. "{chain_a}" and "{chain_b}"')

        visited[resolved_path] = current_chain
        doc = load_nodl(resolved_path, resolve=False)
        children = [_resolve_ref(r.ref, chain=current_chain, origin=resolved_path) for r in (doc.include or [])]

        return IncludedDocument(ref=ref, doc=doc, resolved_includes=children)

    root_children = [_resolve_ref(r.ref, chain=[], origin=origin) for r in (doc.include or [])]

    return DocumentTree(root_doc=doc, resolved_includes=root_children)


def parse_nodl(data: Union[str, bytes, IO]) -> NodlDocument:
    data = yaml.safe_load(data)
    if not isinstance(data, dict):
        raise ValueError('NoDL document must be a YAML/JSON mapping at the top level')

    validate(data)

    # parse_obj is pydantic v1 API, retained as a deprecated alias in v2.
    # Used so this module works against both rosdep-shipped pydantic v1 (humble/jazzy/kilted) and v2 (lyrical+).
    doc = NodlDocument.parse_obj(data)

    return doc


def load_nodl(source: Path, *, resolve: bool = True) -> NodlDocument:
    """Load and validate a NoDL document from a path containing JSON or YAML text.

    When ``resolve`` (default True), ``include`` references are resolved and merged into the resulting document,
    which then has no ``include`` key.
    Pass ``resolve=False`` to parse the document as authored, leaving ``include`` intact.

    Raises jsonschema.ValidationError on schema error
    Raises pydantic.ValidationError on type error
    Raises composition.ResolutionError when no appropriate resolver found for reference
        Resolvers generally raise ResolutionError on invalid or unfindable references,
        but their custom exceptions are allowed propagate for unforseen cases, for visibility
    """
    if resolve:
        result_doc, _ = load_nodl_with_doc_tree(source)
    else:
        result_doc = parse_nodl(source.read_text())

    return result_doc


def load_nodl_with_doc_tree(source: Path) -> tuple[NodlDocument, DocumentTree]:
    """Load, validate, resolve includes, and return both the merged document and the inclusion tree.

    Returns a ``(merged_doc, doc_tree)`` tuple where:

    - ``merged_doc`` is the fully resolved document (no ``include`` key), identical to
      what ``load_nodl(source)`` would return.
    - ``doc_tree`` is the :class:`DocumentTree` capturing the recursive structure of the document includes.

    Raises jsonschema.ValidationError on schema error
    Raises pydantic.ValidationError on type error
    Raises composition.ResolutionError when no appropriate resolver found for reference
        Resolvers generally raise ResolutionError on invalid or unfindable references,
        but their custom exceptions are allowed propagate for unforseen cases, for visibility
    """
    doc = parse_nodl(source.read_text())
    doc_tree = resolve_document(doc, source)
    merged_doc = merge_documents(doc_tree.flatten())
    return merged_doc, doc_tree


def dump_nodl(doc: Union[NodlDocument, dict], *, format: str = 'yaml') -> str:
    """Serialize a NodlDocument (or plain dict) to YAML or JSON string."""
    if isinstance(doc, NodlDocument):
        data = json.loads(doc.json(exclude_none=True))
        data = {key: value for key, value in data.items()}
    else:
        data = doc

    if format == 'json':
        return json.dumps(data, indent=2)
    elif format == 'yaml':
        return yaml.dump(data, default_flow_style=False, allow_unicode=True)
    else:
        raise ValueError(f'Unsupported format "{format}" for nodl serialization')
