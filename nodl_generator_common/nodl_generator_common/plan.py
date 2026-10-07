# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Walk a NoDL document tree to plan what a generator owns."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import Callable, Generic, Optional, TypeVar

from nodl_schema.composition import merge_documents
from nodl_schema.loader import DocumentTree, IncludedDocument, load_nodl_with_doc_tree
from nodl_schema.models import NodlDocument
from nodl_schema.schema import schema_validator

# The generator's parsed ``codegen.<key>`` model, such as ``CodegenCpp``.
ConfigT = TypeVar('ConfigT')


@dataclass(frozen=True)
class CodegenSchema(Generic[ConfigT]):
    """A generator's ``codegen.<key>`` metadata: its key, JSON schema file, and parse into a typed config.

    ``parse`` receives the schema-valid ``codegen.<key>`` object,
    and may raise :class:`jsonschema.ValidationError` for checks the schema cannot express.
    """

    key: str
    schema: Path
    parse: Callable[[dict], ConfigT]

    def load(self, codegen: Optional[dict]) -> Optional[ConfigT]:
        """Validate and parse ``codegen.<key>``, or return ``None`` if it is absent.

        Raises :class:`jsonschema.ValidationError` on schema violation.
        """
        config = (codegen or {}).get(self.key)
        if config is None:
            return None
        schema_validator(self.schema).validate(config)
        return self.parse(config)


class CodegenError(Exception):
    """Raised when a planned document tree is not a valid target for a generator.

    For example, conflicting base classes, or a missing base class.
    """


class Walk(Enum):
    """What the walk does with an included document."""

    CONTINUE = auto()
    """Generate the document and walk into its includes."""
    STOP = auto()
    """Neither generate the document nor walk into its includes."""


class CodegenPlanner(ABC, Generic[ConfigT]):
    """A generator's rules for the documents of a tree, accumulated over one walk.

    The generator reads its results from the planner after :func:`plan` returns.
    """

    @abstractmethod
    def root(self, config: Optional[ConfigT]) -> None:
        """Visit the root document's config. The root is always generated."""

    @abstractmethod
    def visit(self, included: IncludedDocument, config: Optional[ConfigT]) -> Walk:
        """Visit an included document's config, and decide whether the walk continues into it."""

    @abstractmethod
    def finalize(self) -> None:
        """Complete the planner's results once the walk is done.

        Raises :class:`CodegenError` for errors collected during the walk.
        """


@dataclass(frozen=True)
class CodegenPlan:
    """The result of planning generation from a NoDL source.

    - ``doc``: the merged root and every included document the walk continued into.
    - ``sources``: the resolved source path plus every included path.
    """

    doc: NodlDocument
    sources: list[Path]


def walk_tree(
    doc_tree: DocumentTree, codegen: CodegenSchema[ConfigT], planner: CodegenPlanner[ConfigT]
) -> NodlDocument:
    """Walk *doc_tree* breadth-first, visiting each reached document with *planner*.

    Returns the merged document of the root and every included document the walk continued into.
    """
    planner.root(codegen.load(doc_tree.root_doc.codegen))
    to_generate = [doc_tree.root_doc]
    queue = deque(doc_tree.resolved_includes)
    while queue:
        included = queue.popleft()
        if planner.visit(included, codegen.load(included.doc.codegen)) is Walk.CONTINUE:
            to_generate.append(included.doc)
            queue.extend(included.resolved_includes)
    return merge_documents(to_generate)


def plan(source: Path, codegen: CodegenSchema[ConfigT], planner: CodegenPlanner[ConfigT]) -> CodegenPlan:
    """Load *source*, walk its document tree with *planner*, and finalize the planner."""
    # Merging the whole tree reports name collisions, including in documents that are not generated.
    _, doc_tree = load_nodl_with_doc_tree(source)
    doc = walk_tree(doc_tree, codegen, planner)
    sources = [source.resolve(), *(path.resolve() for path in doc_tree.included_paths())]
    planner.finalize()
    return CodegenPlan(doc=doc, sources=sources)
