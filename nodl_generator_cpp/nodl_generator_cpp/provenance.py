# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""C++ adapter over the shared provenance core.

The barrier walk itself lives in :mod:`nodl_generator_common.provenance`; this
module only selects the ``codegen.cpp`` key and parses it into :class:`CodegenCpp`,
the predicate that defines a barrier for the C++ generator.
"""

from __future__ import annotations

from typing import Optional

from nodl_generator_cpp.models import CodegenCpp
from nodl_generator_cpp.schema import load as load_codegen_cpp
from nodl_schema.models import NodlDocument


def codegen_cpp(doc: NodlDocument) -> Optional[CodegenCpp]:
    """Load the ``codegen.cpp`` metadata from a document, or None.

    The ``extract_config`` adapter passed to
    :func:`nodl_generator_common.provenance.build_provenance_map`.
    """
    if doc.codegen is None:
        return None
    return load_codegen_cpp(doc.codegen)
