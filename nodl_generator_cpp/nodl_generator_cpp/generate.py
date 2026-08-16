# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
import re
from dataclasses import dataclass
from typing import IO, Union

from nodl_generator_cpp.models import CodegenCpp, Role
from nodl_generator_cpp.provenance import build_provenance_map
from nodl_schema.loader import load_nodl_with_doc_tree

_IDENTIFIER_RE = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')


class CodegenError(Exception):
    """Raised when codegen-specific validation fails.

    Covers provenance errors such as conflicting base classes,
    missing codegen metadata, and unsupported codegen roles.
    """


@dataclass
class GeneratedFile:
    filename: str
    content: str


def _validate_target_name(target_name: str) -> None:
    """Validate that *target_name* is a valid C++ identifier.

    Raises :class:`ValueError` if the name is empty or not a valid
    C++ identifier (letter or underscore followed by alphanumerics/underscores).
    """
    if not target_name or not _IDENTIFIER_RE.match(target_name):
        raise ValueError(f'target_name must be a valid C++ identifier, got {target_name!r}')


def _find_base_class_config(barriers: list[CodegenCpp]) -> CodegenCpp:
    """Find the single base-class config from the provenance barriers.

    Filters *barriers* to those with ``role == BASE_CLASS`` and ensures
    exactly one exists.

    Returns the single :class:`CodegenCpp` base-class descriptor.

    Raises :class:`CodegenError` if there is no base class or if
    multiple conflicting base classes are found.
    """
    base_classes = [b for b in barriers if b.role is Role.BASE_CLASS]
    if not base_classes:
        raise CodegenError(
            'No base class found. Include a base-class provider (e.g. nodl://rclcpp/node) in your NoDL document.'
        )
    if len(base_classes) > 1:
        classes = ', '.join(b.class_ for b in base_classes if b.class_ is not None)
        raise CodegenError(
            f'Multiple conflicting base class providers found: {classes}. '
            'A generated node can only inherit from one base class.'
        )
    return base_classes[0]


def generate_cpp(source: Union[str, bytes, IO], target_name: str) -> list[GeneratedFile]:
    """Generate C++ base-node class files from a NoDL document.

    Loads and resolves the NoDL document from *source* (string, bytes, or
    file-like object), walks the include tree for provenance, and renders
    the C++ header and source files.

    Returns a list of :class:`GeneratedFile` objects ready to be written
    to disk by the caller.
    """
    _validate_target_name(target_name)

    merged_doc, doc_tree = load_nodl_with_doc_tree(source)
    barriers, provenance_map = build_provenance_map(doc_tree)

    base_class = _find_base_class_config(barriers)

    print(base_class)

    # TODO: filter merged_doc entities against provenance_map, template rendering
    return []
