# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Models for the Node composition schema (``node.schema.yaml``).

These are hand-written rather than emitted into the generated ``models.py``
because the Node schema's ``main``/``mixins`` reference the document schema
across files, which datamodel-codegen can only express as a multi-module
package -- not the single ``models.py`` the rest of nodl_schema imports. Keep
this in sync with ``node.schema.yaml`` by hand; it is a small, stable surface.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional, Union

try:
    from pydantic.v1 import BaseModel, Extra, Field
except ImportError:
    from pydantic import BaseModel, Extra, Field

from nodl_schema.models import NodlDocument


class Base(Enum):
    """Built-in ROS 2 base node type whose interface a node inherits."""

    node = 'node'
    lifecycle_node = 'lifecycle_node'


class Node(BaseModel):
    """A NoDL Node: a whole ROS 2 node interface composed from base + mixins + main."""

    class Config:
        extra = Extra.forbid

    nodl_version: int = Field(2, const=True, description='NoDL schema major version this document targets.')
    base: Optional[Base] = Field(
        None,
        description='Built-in ROS 2 base node type whose interface this node inherits.',
    )
    main: NodlDocument = Field(
        ...,
        description="The interface this node's implementation owns, as an in-place NoDL document.",
    )
    mixins: Optional[list[Union[str, NodlDocument]]] = Field(
        None,
        description='NoDL documents merged in for documentation and conformance; ignored by code generation.',
    )
