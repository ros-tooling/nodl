"""Graph introspection to produce a rosgraph_msgs.msg.Node representation."""

from __future__ import annotations

import time

import rclpy
import rclpy.executors
from builtin_interfaces.msg import Duration
from rcl_interfaces.srv import DescribeParameters, ListParameters
from rosgraph_msgs.msg import Action, InterfaceType
from rosgraph_msgs.msg import Node as NodeMsg
from rosgraph_msgs.msg import QoSProfile as RosQoS
from rosgraph_msgs.msg import Service, Topic


def _ns_to_duration(ns: int) -> Duration:
    return Duration(sec=ns // 1_000_000_000, nanosec=ns % 1_000_000_000)


def _rclpy_qos_to_ros_qos(rclpy_qos) -> RosQoS:
    """Convert rclpy.qos.QoSProfile to rosgraph_msgs.msg.QoSProfile."""
    q = RosQoS()
    q.history = rclpy_qos.history.value
    q.depth = rclpy_qos.depth
    q.reliability = rclpy_qos.reliability.value
    q.durability = rclpy_qos.durability.value
    q.liveliness = rclpy_qos.liveliness.value
    q.deadline = _ns_to_duration(rclpy_qos.deadline.nanoseconds)
    q.lifespan = _ns_to_duration(rclpy_qos.lifespan.nanoseconds)
    q.liveliness_lease_duration = _ns_to_duration(rclpy_qos.liveliness_lease_duration.nanoseconds)
    return q


def _get_topic_qos(
    node, topic_name: str, node_name: str, node_namespace: str, is_publisher: bool
) -> RosQoS:
    """Return RosQoS for a specific node's topic endpoint, or a default if not found."""
    fqn = f'{node_namespace}/{node_name}'.replace('//', '/')
    infos = (
        node.get_publishers_info_by_topic(topic_name)
        if is_publisher
        else node.get_subscriptions_info_by_topic(topic_name)
    )
    for info in infos:
        info_fqn = f'{info.node_namespace}/{info.node_name}'.replace('//', '/')
        if info_fqn == fqn:
            return _rclpy_qos_to_ros_qos(info.qos_profile)
    return RosQoS()


def _call_service_sync(node, client, request, timeout_sec: float = 5.0):
    """Make a synchronous service call, returning the result or None on timeout."""
    if not client.wait_for_service(timeout_sec=timeout_sec):
        return None
    future = client.call_async(request)
    rclpy.spin_until_future_complete(node, future, timeout_sec=timeout_sec)
    return future.result()


def _get_parameters(node, target_node_fqn: str) -> tuple[list, list]:
    """Fetch ParameterDescriptors from a running node via its parameter services."""
    list_client = node.create_client(ListParameters, f'{target_node_fqn}/list_parameters')
    response = _call_service_sync(node, list_client, ListParameters.Request())
    node.destroy_client(list_client)

    if response is None:
        return [], []

    param_names = list(response.result.names)
    if not param_names:
        return [], []

    describe_client = node.create_client(
        DescribeParameters, f'{target_node_fqn}/describe_parameters'
    )
    req = DescribeParameters.Request()
    req.names = param_names
    desc_response = _call_service_sync(node, describe_client, req)
    node.destroy_client(describe_client)

    if desc_response is None:
        return [], []

    return list(desc_response.descriptors), []


def _spin_briefly(node, duration_sec: float) -> None:
    """Spin briefly to allow graph discovery to settle."""
    executor = rclpy.executors.SingleThreadedExecutor()
    executor.add_node(node)
    deadline = time.time() + duration_sec
    while time.time() < deadline:
        executor.spin_once(timeout_sec=0.1)
    executor.remove_node(node)


def describe(node_name: str, *, discovery_timeout_sec: float = 2.0) -> NodeMsg:
    """Introspect a running ROS 2 node and return a rosgraph_msgs.msg.Node.

    node_name: fully qualified node name, e.g. '/my_ns/my_node' or '/my_node'.
    discovery_timeout_sec: time to wait for graph discovery before introspecting.

    Raises RuntimeError if the node is not found in the graph.
    Initializes rclpy if not already initialized; shuts it down only if this
    call initialized it.
    """
    node_name = node_name if node_name.startswith('/') else f'/{node_name}'

    idx = node_name.rfind('/')
    if idx <= 0:
        namespace = '/'
        short_name = node_name.lstrip('/')
    else:
        namespace = node_name[:idx]
        short_name = node_name[idx + 1:]

    initialized_here = not rclpy.ok()
    if initialized_here:
        rclpy.init()

    introspect_node = rclpy.create_node('_nodl_describer')
    try:
        _spin_briefly(introspect_node, discovery_timeout_sec)

        known = introspect_node.get_node_names_and_namespaces()
        if (short_name, namespace) not in known:
            raise RuntimeError(
                f"Node '{node_name}' not found in the graph. "
                f"Available: {[(n, ns) for n, ns in known]}"
            )

        publishers = [
            Topic(
                name=topic,
                type=InterfaceType(name=types[0] if types else ''),
                qos=_get_topic_qos(introspect_node, topic, short_name, namespace, True),
            )
            for topic, types in introspect_node.get_publisher_names_and_types_by_node(
                short_name, namespace
            )
        ]

        subscriptions = [
            Topic(
                name=topic,
                type=InterfaceType(name=types[0] if types else ''),
                qos=_get_topic_qos(introspect_node, topic, short_name, namespace, False),
            )
            for topic, types in introspect_node.get_subscriber_names_and_types_by_node(
                short_name, namespace
            )
        ]

        action_server_info = introspect_node.get_action_server_names_and_types_by_node(
            short_name, namespace
        )
        action_client_info = introspect_node.get_action_client_names_and_types_by_node(
            short_name, namespace
        )

        action_servers = [
            Action(
                name=action_name,
                send_goal=Service(
                    request_type=InterfaceType(name=types[0] if types else '')
                ),
            )
            for action_name, types in action_server_info
        ]

        action_clients = [
            Action(
                name=action_name,
                send_goal=Service(
                    request_type=InterfaceType(name=types[0] if types else '')
                ),
            )
            for action_name, types in action_client_info
        ]

        service_servers = [
            Service(
                name=srv_name,
                request_type=InterfaceType(name=types[0] if types else ''),
                response_type=InterfaceType(name=types[0] if types else ''),
            )
            for srv_name, types in introspect_node.get_service_names_and_types_by_node(
                short_name, namespace
            )
            if '/_action/' not in srv_name
        ]

        service_clients = [
            Service(
                name=srv_name,
                request_type=InterfaceType(name=types[0] if types else ''),
                response_type=InterfaceType(name=types[0] if types else ''),
            )
            for srv_name, types in introspect_node.get_client_names_and_types_by_node(
                short_name, namespace
            )
            if '/_action/' not in srv_name
        ]

        parameters, parameter_values = _get_parameters(introspect_node, node_name)

        return NodeMsg(
            name=node_name,
            parameters=parameters,
            parameter_values=parameter_values,
            publishers=publishers,
            subscriptions=subscriptions,
            service_servers=service_servers,
            service_clients=service_clients,
            action_servers=action_servers,
            action_clients=action_clients,
        )

    finally:
        introspect_node.destroy_node()
        if initialized_here:
            rclpy.shutdown()
