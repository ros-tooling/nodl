# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
import json
from collections import deque
from dataclasses import dataclass
from typing import IO, TypeAlias, Union
from pathlib import Path

import yaml

from nodl_schema.composition import ResolutionError, merge_documents, normalize, resolve
from nodl_schema.local_resolver import path_to_ref
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


def resolve_document(doc: NodlDocument) -> DocumentTree:
    # DFS traversal of the includes, detecting non-tree double-inclusions/cycles
    # NOTE(emerson) there is not currently a way to detect if a reference loops back to _this_ document,
    # since we don't have our own ref in this context.
    # Really, we are depending on the package dependency graph to avoid cycles.
    # Additionally, if "the same" reference were to be found by different resolvers, that is not caught here,
    # but by merge collision checking.

    visited: dict[Ref, IncludeChain] = {}

    def _resolve_ref(ref: Ref, chain: IncludeChain) -> IncludedDocument:
        current_chain = chain + [ref]

        if ref in visited:
            other_chain = visited[ref]
            chain_a = ' > '.join(current_chain)
            chain_b = ' > '.join(other_chain)
            raise ResolutionError(f'Double-inclusion detected. "{chain_a}" and "{chain_b}"')

        visited[ref] = current_chain
        content = resolve(ref)
        doc = load_nodl(content, resolve=False)
        children = [_resolve_ref(r.ref, current_chain) for r in (doc.include or [])]

        return IncludedDocument(ref=ref, doc=doc, resolved_includes=children)


def resolve_document(doc: NodlDocument, origin: str | None = None) -> list[NodlDocument]:
    """Return ``doc`` followed by every document it includes, breadth-first.

    ``origin`` is the normalized reference ``doc`` itself came from, if it has one.
    It is what relative references inside ``doc`` are resolved against, and it lets a reference
    that loops back to ``doc`` be caught like any other cycle.

    Each reference is normalized before use, so the same document reached by two different
    spellings is recognized as one. Raises ResolutionError on a cycle or double inclusion.
    """
    visited: dict[str, list[str]] = {}
    if origin is not None:
        visited[origin] = [origin]

    ref_queue: deque[tuple[str, str | None, list[str]]] = deque((r.ref, origin, []) for r in (doc.include or []))
    results = [doc]

    while ref_queue:
        ref, parent, path = ref_queue.popleft()
        # Normalizing before the check means two spellings of one document collide here
        # rather than recursing until something else gives way.
        this_ref = normalize(ref, parent)
        this_path = path + [this_ref]

        if this_ref in visited:
            path_a = ' > '.join(this_path)
            path_b = ' > '.join(visited[this_ref])
            raise ResolutionError(f'Double-inclusion detected. "{path_a}" and "{path_b}"')

        included_doc = load_nodl(resolve(this_ref), resolve=False)

        visited[this_ref] = this_path
        results.append(included_doc)
        ref_queue.extend((r.ref, this_ref, this_path) for r in (included_doc.include or []))

    root_children = [_resolve_ref(r.ref, chain=[]) for r in (doc.include or [])]

    return DocumentTree(root_doc=doc, resolved_includes=root_children)


def _load_doc(source: Union[str, bytes, IO]) -> NodlDocument:
    data = yaml.safe_load(source)
    if not isinstance(data, dict):
        raise ValueError('NoDL document must be a YAML/JSON mapping at the top level')

    validate(data)

    # parse_obj is pydantic v1 API, retained as a deprecated alias in v2.
    # Used so this module works against both rosdep-shipped pydantic v1 (humble/jazzy/kilted) and v2 (lyrical+).
    doc = NodlDocument.parse_obj(data)

    return doc


def load_nodl(
    source: Union[str, bytes, IO], *, resolve: bool = True, base: Union[str, Path, None] = None
) -> NodlDocument:
    """Load and validate a NoDL document from a string, bytes, or file-like object containing JSON or YAML text.

    When ``resolve`` (default True), ``include`` references are resolved and merged into the resulting document,
    which then has no ``include`` key.
    Pass ``resolve=False`` to parse the document as authored, leaving ``include`` intact.

    ``base`` is the path this document was read from.
    Relative references resolve against its directory, so it is required for a document that uses
    them and ignored for one that does not. An open file supplies it automatically.

    Raises jsonschema.ValidationError on schema error
    Raises pydantic.ValidationError on type error
    Raises composition.ResolutionError when no appropriate resolver found for reference
        Resolvers generally raise ResolutionError on invalid or unfindable references,
        but their custom exceptions are allowed propagate for unforseen cases, for visibility
    """

    if resolve:
        result_doc, _ = load_nodl_with_doc_tree(source)
    if base is None:
        # An open file knows where it came from, so a caller reading a path need not pass it twice.
        name = getattr(source, 'name', None)
        if isinstance(name, (str, Path)):
            base = name

    data = yaml.safe_load(source)
    if not isinstance(data, dict):
        raise ValueError('NoDL document must be a YAML/JSON mapping at the top level')

    validate(data)

    # parse_obj is pydantic v1 API, retained as a deprecated alias in v2.
    # Used so this module works against both rosdep-shipped pydantic v1 (humble/jazzy/kilted) and v2 (lyrical+).
    doc = NodlDocument.parse_obj(data)

    if resolve:
        all_docs = resolve_document(doc, path_to_ref(base) if base is not None else None)
        result_doc = merge_documents(all_docs)
    else:
        result_doc = _load_doc(source)

    return result_doc


def load_nodl_with_doc_tree(source: Union[str, bytes, IO]) -> tuple[NodlDocument, DocumentTree]:
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
    doc = _load_doc(source)
    doc_tree = resolve_document(doc)
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
