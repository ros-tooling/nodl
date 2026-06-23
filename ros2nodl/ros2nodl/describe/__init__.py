# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Public API for converting an observed Node message to a NoDL draft."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from nodl_schema.models import NodlDocument


@dataclass(frozen=True)
class Gap:
    """A field that could not be recovered reliably from the observation."""

    path: str
    reason: str


@dataclass
class DescribeOptions:
    include_parameters: bool = True
    keep_hidden: bool = False


@dataclass
class DescribeResult:
    doc: 'NodlDocument'
    gaps: List[Gap] = field(default_factory=list)


def node_to_nodl(node, opts: Optional[DescribeOptions] = None) -> DescribeResult:
    """Convert a duck-typed ``rosgraph_msgs/Node`` into a NoDL document."""
    from ros2nodl.describe._transform import convert

    return convert(node, opts or DescribeOptions())
