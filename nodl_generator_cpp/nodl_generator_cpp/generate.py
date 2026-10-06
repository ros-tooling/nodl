# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
import re
from collections import deque
from dataclasses import dataclass
from pathlib import Path

from nodl_generator_common.generated_file import GeneratedFile
from nodl_generator_cpp.cmake_deps import (
    format_cmake_deps,
    generated_filenames,
    ros_deps,
)
from nodl_generator_cpp.include_prefix import validate_include_prefix
from nodl_generator_cpp.models import CodegenCpp, Role
from nodl_generator_cpp.params import generate_genparamlib_yaml
from nodl_generator_cpp.schema import load as load_codegen_cpp
from nodl_generator_cpp.template import render_templates
from nodl_schema.composition import merge_documents
from nodl_schema.loader import DocumentTree, load_nodl_with_doc_tree
from nodl_schema.models import NodlDocument

_IDENTIFIER_RE = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')


class CodegenError(Exception):
    """Raised when codegen-specific validation fails.

    Covers errors such as conflicting base classes,
    missing codegen metadata, and unsupported codegen roles.
    """


@dataclass(frozen=True)
class _Plan:
    """What the generator owns, read from the document tree.

    - ``bases``: the ``BASE_CLASS`` configs of included documents the walk reached.
    - ``doc``: the merged document of everything the generator owns,
      which is the root plus every included document without ``codegen.cpp``.
    - ``sources``: the resolved NoDL source path plus every included path.
    """

    bases: list[CodegenCpp]
    doc: NodlDocument
    sources: list[Path]


def _plan_tree(doc_tree: DocumentTree) -> tuple[list[CodegenCpp], NodlDocument]:
    """Walk *doc_tree* and split it into base classes and the document the generator owns.

    An included document with ``codegen.cpp`` already has an implementation,
    so the walk does not descend into it.
    Its role decides what it contributes: ``BASE_CLASS`` its class, ``NO_GENERATE`` nothing.
    Every other document is owned, and the walk continues into its includes.
    The walk is breadth-first, matching the order of the fully merged document.
    """
    bases: list[CodegenCpp] = []
    owned = [doc_tree.root_doc]
    queue = deque(doc_tree.resolved_includes)
    while queue:
        included = queue.popleft()
        config = load_codegen_cpp(included.doc.codegen) if included.doc.codegen else None
        if config is None:
            owned.append(included.doc)
            queue.extend(included.resolved_includes)
        elif config.role is Role.BASE_CLASS:
            bases.append(config)
    return bases, merge_documents(owned)


def _plan(source: Path) -> _Plan:
    """Load *source* and plan generation from its document tree.

    Loading still merges the whole tree, so name collisions anywhere in it are reported.
    """
    _, doc_tree = load_nodl_with_doc_tree(source)
    bases, doc = _plan_tree(doc_tree)
    sources = [source.resolve(), *(path.resolve() for path in doc_tree.included_paths())]
    return _Plan(bases=bases, doc=doc, sources=sources)


def _validate_target_name(target_name: str) -> None:
    """Validate that *target_name* is a valid C++ identifier.

    Raises :class:`ValueError` if the name is empty or not a valid
    C++ identifier (letter or underscore followed by alphanumerics/underscores).
    """
    if not target_name or not _IDENTIFIER_RE.match(target_name):
        raise ValueError(f'target_name must be a valid C++ identifier, got {target_name!r}')


def _find_base_class_config(base_classes: list[CodegenCpp]) -> tuple[str, str]:
    """Find the single base-class config.

    Ensures exactly one of *base_classes* exists.

    Returns ``(class, header)`` — the C++ class name and its header.

    Raises :class:`CodegenError` if there is no base class or if
    multiple conflicting base classes are found.
    """
    if not base_classes:
        raise CodegenError(
            'No base class found. Include a base-class provider '
            '(e.g. nodl://nodl_common_interfaces/node) in your NoDL document.'
        )
    if len(base_classes) > 1:
        classes = ', '.join(b.class_ for b in base_classes if b.class_ is not None)
        raise CodegenError(
            f'Multiple conflicting base class providers found: {classes}. '
            'A generated node can only inherit from one base class.'
        )
    assert base_classes[0].class_ is not None
    assert base_classes[0].header is not None
    return base_classes[0].class_, base_classes[0].header


@dataclass
class CmakeDepsResult:
    """Data needed to write a ``<target>_deps.cmake`` file."""

    sources: list[Path]
    ros_deps: list[str]
    generated_filenames: list[str]

    def format(self, target: str) -> str:
        """Render the CMake deps file content."""
        return format_cmake_deps(target, self.sources, self.ros_deps, self.generated_filenames)


def cmake_deps(source: Path, target_name: str, *, include_prefix: str | None = None) -> CmakeDepsResult:
    """Compute CMake dependency information from a NoDL document.

    Plans generation the same way as :func:`generate_cpp` but stops before template rendering.

    Returns a :class:`CmakeDepsResult` containing the NoDL source paths, ROS package dependencies,
    and the list of files the generator will produce.
    The file paths are relative to the output directory and include *include_prefix* for headers.
    """
    _validate_target_name(target_name)
    validate_include_prefix(include_prefix)

    plan = _plan(source)
    doc = plan.doc

    _find_base_class_config(plan.bases)  # validates single base class

    has_parameters = bool(doc.parameters)

    return CmakeDepsResult(
        sources=plan.sources,
        ros_deps=ros_deps(
            plan.bases,
            doc.publishers or [],
            doc.subscriptions or [],
            doc.service_servers or [],
            doc.service_clients or [],
            doc.action_servers or [],
            doc.action_clients or [],
        ),
        generated_filenames=generated_filenames(target_name, has_parameters, include_prefix=include_prefix),
    )


def generate_cpp(source: Path, target_name: str, *, include_prefix: str | None = None) -> list[GeneratedFile]:
    """Generate C++ base-node class files from a NoDL document.

    Loads and resolves the NoDL document at *source* (a filesystem path),
    walks the include tree for the documents it owns and its base class,
    and renders the C++ header and source files.

    When *include_prefix* is given, the header is placed under it and the source includes it from there.
    The ``filename`` of each returned file is relative to the output directory.

    Returns a list of :class:`GeneratedFile` objects ready to be written
    to disk by the caller.
    """
    _validate_target_name(target_name)
    validate_include_prefix(include_prefix)

    plan = _plan(source)
    doc = plan.doc

    base_class, base_header = _find_base_class_config(plan.bases)

    has_parameters = bool(doc.parameters)

    generated_files = []
    generated_files += render_templates(
        target_name,
        base_class,
        base_header,
        doc.publishers or [],
        doc.subscriptions or [],
        doc.service_servers or [],
        doc.service_clients or [],
        doc.action_servers or [],
        doc.action_clients or [],
        has_parameters,
        include_prefix=include_prefix,
    )
    if has_parameters:
        generated_files += [generate_genparamlib_yaml(target_name, doc.parameters)]

    return generated_files
