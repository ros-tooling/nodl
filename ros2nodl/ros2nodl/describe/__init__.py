# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Public API for describing observed and live ROS nodes as NoDL."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING
from uuid import uuid4

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
    doc: NodlDocument
    gaps: list[Gap] = field(default_factory=list)


def describe_node(
    node_name: str,
    *,
    timeout_sec: float = 5.0,
    options: DescribeOptions | None = None,
) -> DescribeResult:
    """Describe one running ROS node."""
    from ros2nodl.describe._source import acquire_live

    opts = options or DescribeOptions()
    node = acquire_live(
        node_name,
        timeout_sec=timeout_sec,
        include_parameters=opts.include_parameters,
        topic=f'/nodl/observed_node_{uuid4().hex}',
    )
    return node_to_nodl(node, opts)


def node_to_nodl(node, opts: DescribeOptions | None = None) -> DescribeResult:
    """Convert a duck-typed ``rosgraph_msgs/Node`` into a NoDL document."""
    from ros2nodl.describe._transform import convert

    return convert(node, opts or DescribeOptions())
