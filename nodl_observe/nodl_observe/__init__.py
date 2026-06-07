# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Observe a running ROS node, producing a ``rosgraph_msgs/Node`` message.

Stage one of the Observe -> Describe pipeline (#68): records *everything
observable* about a live node -- every publisher, subscription, service and
action endpoint with its actual QoS and type hash where available, plus the
node's parameters and their current values -- without interpreting any of it.
Interpretation (dropping infrastructure endpoints, mapping to NoDL) belongs to
Describe (#53).

The public entry point is :func:`observe_node`.
"""

import time

import rclpy
from rclpy.action.graph import (
    get_action_client_names_and_types_by_node,
    get_action_server_names_and_types_by_node,
)
from rosgraph_msgs.msg import Node as NodeMsg

from ._endpoints import (
    build_service_endpoints,
    build_topic_endpoints,
    fold_actions,
)
from ._parameters import collect_parameters
from ._qos import latched_qos

__all__ = ['observe_node', 'NodeNotFoundError', 'latched_qos']

# Graph stability poll parameters.  There is no "discovery complete" signal, so
# we poll until the target's endpoint set is unchanged across this many
# consecutive samples, bounded by the overall timeout.
_STABLE_POLLS = 3
_POLL_INTERVAL_SEC = 0.2


class NodeNotFoundError(Exception):
    """The target node never appeared in the graph within ``timeout_sec``."""


def observe_node(
    node,
    target_fqn: str,
    *,
    timeout_sec: float = 5.0,
    include_parameters: bool = True,
) -> NodeMsg:
    """Observe a running node and return its runtime ``rosgraph_msgs/Node``.

    :param node: a caller-provided, already-initialised ``rclpy`` node used for
        all graph queries and parameter service calls.  ``observe_node`` never
        creates or spins up its own node.
    :param target_fqn: fully-qualified name of the node to observe, e.g.
        ``/ns/talker``.  Hidden (``_``-prefixed) nodes work too -- nothing is
        filtered.
    :param timeout_sec: a *ceiling*, not a fixed duration.  It bounds (1) the
        wait for DDS discovery to populate this observer's graph cache -- the
        graph is polled until the target's endpoint set is stable for a few
        consecutive samples and returns as soon as it settles -- and (2) the
        parameter service round-trips, which share whatever budget discovery
        left over.  Only a missing/unresponsive target burns the full budget.
    :param include_parameters: when ``False``, skip the remote parameter
        services entirely (the only part of observation that contacts the
        target node); parameter arrays come back empty.
    :returns: a fully-populated ``rosgraph_msgs/Node`` message with all endpoint
        arrays sorted (by name, then type) for deterministic output.
    :raises NodeNotFoundError: if the target never appears in the graph within
        ``timeout_sec``.

    .. note::
        The caller is responsible for the node's executor.  Parameter
        collection drives async service futures via
        ``rclpy.spin_until_future_complete(node, future, ...)`` internally, so
        a plain initialised node (as a ros2cli verb provides) is sufficient --
        the caller must *not* be spinning the node on another thread at the same
        time.
    """
    deadline = time.monotonic() + timeout_sec
    name, namespace = _wait_for_node(node, target_fqn, deadline)
    snapshot = _wait_for_stable_graph(node, name, namespace, deadline)

    msg = NodeMsg()
    msg.name = target_fqn

    _collect_endpoints(node, name, namespace, msg, snapshot)

    if include_parameters:
        remaining = max(0.0, deadline - time.monotonic())
        descriptors, values = collect_parameters(node, target_fqn, remaining)
        msg.parameters = descriptors
        msg.parameter_values = values

    return msg


def _split_fqn(target_fqn: str):
    """Split a fully-qualified node name into ``(name, namespace)``.

    ``/ns/sub/talker`` -> ``('talker', '/ns/sub')``; ``/talker`` ->
    ``('talker', '/')``.  These are the two arguments the by-node graph queries
    expect.
    """
    stripped = target_fqn.rstrip('/')
    if '/' not in stripped:
        return stripped, '/'
    name = stripped.rsplit('/', 1)[1]
    namespace = stripped.rsplit('/', 1)[0]
    if namespace == '':
        namespace = '/'
    return name, namespace


def _wait_for_node(node, target_fqn, deadline):
    """Poll the graph until the target node appears, returning (name, namespace).

    :raises NodeNotFoundError: if the deadline passes without the node showing.
    """
    name, namespace = _split_fqn(target_fqn)
    while True:
        for n, ns in node.get_node_names_and_namespaces():
            if n == name and ns.rstrip('/') == namespace.rstrip('/'):
                return name, namespace
        if time.monotonic() >= deadline:
            raise NodeNotFoundError(
                f"Node '{target_fqn}' did not appear in the graph within the timeout.")
        time.sleep(_POLL_INTERVAL_SEC)


def _endpoint_snapshot(node, name, namespace):
    """One snapshot of the target's four by-node endpoint queries."""
    return (
        node.get_publisher_names_and_types_by_node(name, namespace),
        node.get_subscriber_names_and_types_by_node(name, namespace),
        node.get_service_names_and_types_by_node(name, namespace),
        node.get_client_names_and_types_by_node(name, namespace),
    )


def _signature(snapshot):
    """A hashable view of a snapshot, for stability comparison."""
    return tuple(
        tuple(sorted((n, tuple(types)) for n, types in part)) for part in snapshot)


def _wait_for_stable_graph(node, name, namespace, deadline):
    """Poll until the target's endpoint set is stable, bounded by the deadline.

    Returns the last snapshot taken; collection consumes it directly, since
    re-querying after the stability check would both repeat the four graph
    queries and reopen the very race the check just closed.
    """
    snapshot = _endpoint_snapshot(node, name, namespace)
    previous = _signature(snapshot)
    stable_count = 1
    while stable_count < _STABLE_POLLS and time.monotonic() < deadline:
        time.sleep(_POLL_INTERVAL_SEC)
        snapshot = _endpoint_snapshot(node, name, namespace)
        current = _signature(snapshot)
        if current == previous:
            stable_count += 1
        else:
            stable_count = 1
            previous = current
    return snapshot


def _filter_infos_to_node(infos, name, namespace):
    """Group ``TopicEndpointInfo`` objects by topic, keeping only this node's."""
    target_ns = namespace.rstrip('/')
    out = {}
    for topic_name, info_list in infos.items():
        matched = [
            info for info in info_list
            if info.node_name == name and info.node_namespace.rstrip('/') == target_ns
        ]
        if matched:
            out[topic_name] = matched
    return out


def _collect_endpoints(node, name, namespace, msg, snapshot):
    """Fill ``msg`` endpoint arrays from the graph; mutate ``msg`` in place.

    ``snapshot`` is the stable by-node endpoint set returned by
    ``_wait_for_stable_graph``; only the per-topic info queries (QoS + type
    hash) hit the graph from here.
    """
    pubs, subs, srv_servers, srv_clients = snapshot

    pub_infos = _filter_infos_to_node(
        {n: node.get_publishers_info_by_topic(n) for n, _ in pubs}, name, namespace)
    sub_infos = _filter_infos_to_node(
        {n: node.get_subscriptions_info_by_topic(n) for n, _ in subs}, name, namespace)

    publishers = build_topic_endpoints(pubs, pub_infos)
    subscriptions = build_topic_endpoints(subs, sub_infos)
    service_servers = build_service_endpoints(srv_servers)
    service_clients = build_service_endpoints(srv_clients)

    action_servers_nt = get_action_server_names_and_types_by_node(node, name, namespace)
    action_clients_nt = get_action_client_names_and_types_by_node(node, name, namespace)

    # Action servers own server-side services + the feedback/status publishers;
    # action clients own client-side services + the feedback/status
    # subscriptions.  Fold each direction against its matching flat lists.
    action_servers = fold_actions(action_servers_nt, service_servers, publishers)
    action_clients = fold_actions(action_clients_nt, service_clients, subscriptions)

    msg.publishers = publishers
    msg.subscriptions = subscriptions
    msg.service_servers = service_servers
    msg.service_clients = service_clients
    msg.action_servers = action_servers
    msg.action_clients = action_clients
