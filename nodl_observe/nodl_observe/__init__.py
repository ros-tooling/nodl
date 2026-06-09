# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Observe a running ROS node, producing a ``rosgraph_msgs/Node`` message.

Stage one of the Observe -> Describe pipeline (#68): records *everything
observable* about a live node -- every publisher, subscription, service and
action endpoint with its actual QoS and type hash where available, plus the
node's parameters and their current values -- without interpreting any of it.
Interpretation (dropping infrastructure endpoints, mapping to NoDL) belongs to
Describe (#53).

The public surface is :func:`observe_node` (graph orchestration in
:mod:`._observe`), the :func:`nodl_observe.serialization` renderers, and
:func:`latched_qos` for the CLI's latched publish.  The ``_``-prefixed modules
hold pure builders and are not part of the public API.
"""

from ._observe import NodeNotFoundError, observe_node
from ._qos import latched_qos

__all__ = ['observe_node', 'NodeNotFoundError', 'latched_qos']
