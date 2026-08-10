# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
import json
from collections import deque
from typing import IO, Union

import yaml

from nodl_schema.composition import ResolutionError, merge_documents, resolve
from nodl_schema.models import NodlDocument
from nodl_schema.validation import validate


def resolve_document(doc: NodlDocument) -> list[NodlDocument]:
    # Do breadth-first traversal of the includes, detecting non-tree double-inclusions/cycles
    # NOTE(emerson) there is not currently a way to detect if a reference loops back to _this_ document,
    # since we don't have our own ref in this context.
    # Really, we are depending on the package dependency graph to avoid cycles.
    # Additionally, if "the same" reference were to be found by different resolvers, that is not caught here,
    # but by merge collision checking.
    visited: dict[str, list[str]] = {}
    initial_refs = [(r.ref, []) for r in (doc.include or [])]
    ref_queue: deque[tuple[str, list[str]]] = deque(initial_refs)

    results = [doc]

    while ref_queue:
        ref, path = ref_queue.popleft()
        this_path = path + [ref]

        # Detect cycle/double-inclusion
        if ref in visited:
            other_path = visited[ref]
            path_a = ' > '.join(this_path)
            path_b = ' > '.join(other_path)
            raise ResolutionError(f'Double-inclusion detected. "{path_a}" and "{path_b}"')

        # Process
        content = resolve(ref)
        included_doc = load_nodl(content, resolve=False)

        # Accumulate
        visited[ref] = this_path
        results.append(included_doc)
        ref_queue.extend(((r.ref, this_path) for r in (included_doc.include or [])))

    return results


def load_nodl(source: Union[str, bytes, IO], *, resolve: bool = True) -> NodlDocument:
    """Load and validate a NoDL document from a string, bytes, or file-like object containing JSON or YAML text.

    When ``resolve`` (default True), ``include`` references are resolved and merged into the resulting document,
    which then has no ``include`` key.
    Pass ``resolve=False`` to parse the document as authored, leaving ``include`` intact.

    Raises jsonschema.ValidationError on schema error
    Raises pydantic.ValidationError on type error
    Raises composition.ResolutionError when no appropriate resolver found for reference
        Resolvers generally raise ResolutionError on invalid or unfindable references,
        but their custom exceptions are allowed propagate for unforseen cases, for visibility
    """
    data = yaml.safe_load(source)
    if not isinstance(data, dict):
        raise ValueError('NoDL document must be a YAML/JSON mapping at the top level')

    validate(data)

    # parse_obj is pydantic v1 API, retained as a deprecated alias in v2.
    # Used so this module works against both rosdep-shipped pydantic v1 (humble/jazzy/kilted) and v2 (lyrical+).
    doc = NodlDocument.parse_obj(data)

    if resolve:
        all_docs = resolve_document(doc)
        result_doc = merge_documents(all_docs)
    else:
        result_doc = doc

    return result_doc


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
