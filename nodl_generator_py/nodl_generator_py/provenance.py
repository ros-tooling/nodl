# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Python adapter over the shared include-provenance core."""

from typing import Optional

from nodl_generator_py.models import CodegenPython
from nodl_generator_py.schema import load as load_codegen_python
from nodl_schema.models import NodlDocument


def codegen_python(doc: NodlDocument) -> Optional[CodegenPython]:
    """Return a document's validated Python provider metadata, if present."""
    if doc.codegen is None:
        return None
    return load_codegen_python(doc.codegen)
