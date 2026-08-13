# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
from dataclasses import dataclass
from typing import IO, Union

from nodl_schema.loader import load_nodl_with_doc_tree


class CodegenError(Exception):
    """Raised when codegen-specific validation fails.

    Covers provenance errors such as conflicting base classes,
    missing codegen metadata, and unsupported codegen roles.
    """


@dataclass
class GeneratedFile:
    filename: str
    content: str


def generate_cpp(source: Union[str, bytes, IO], target_name: str) -> list[GeneratedFile]:
    """Generate C++ base-node class files from a NoDL document.

    Loads and resolves the NoDL document from *source* (string, bytes, or
    file-like object), walks the include tree for provenance, and renders
    the C++ header and source files.

    Returns a list of :class:`GeneratedFile` objects ready to be written
    to disk by the caller.
    """
    merged_doc, doc_tree = load_nodl_with_doc_tree(source)

    # TODO: provenance walk, template rendering
    return []
