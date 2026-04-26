"""Wire up a node from a NodlDocument: publishers, subscriptions, services, parameters."""
from __future__ import annotations

from nodl.models import NodlDocument
from nodl_rclpy._support import (
    import_ros_type,
    qos_from_spec,
    service_to_identifier,
    topic_to_identifier,
)
from nodl_rclpy.params import NodlParameterListener


def setup_nodl(node, doc: NodlDocument) -> None:
    """Attach publishers, subscriptions, service clients/servers, and parameters to node."""

    if doc.parameters:
        node.param_listener_ = NodlParameterListener(node, doc.parameters)
        node.params_ = node.param_listener_.get_params()

    for pub_spec in (doc.publishers or []):
        msg_type = import_ros_type(pub_spec.type)
        attr = 'pub_' + topic_to_identifier(pub_spec.topic) + '_'
        setattr(node, attr, node.create_publisher(msg_type, pub_spec.topic, qos_from_spec(pub_spec.qos)))

    for sub_spec in (doc.subscriptions or []):
        msg_type = import_ros_type(sub_spec.type)
        ident = topic_to_identifier(sub_spec.topic)
        callback = getattr(node, 'on_' + ident, None)
        if callback is None:
            node.get_logger().warning(
                f"No method 'on_{ident}' for subscription '{sub_spec.topic}'"
            )
            continue
        attr = 'sub_' + ident + '_'
        setattr(node, attr, node.create_subscription(
            msg_type, sub_spec.topic, callback, qos_from_spec(sub_spec.qos)
        ))

    for srv_spec in (doc.service_servers or []):
        srv_type = import_ros_type(srv_spec.type)
        ident = service_to_identifier(srv_spec.name)
        callback = getattr(node, 'on_' + ident, None)
        if callback is None:
            node.get_logger().warning(
                f"No method 'on_{ident}' for service server '{srv_spec.name}'"
            )
            continue
        attr = 'srv_' + ident + '_'
        setattr(node, attr, node.create_service(srv_type, srv_spec.name, callback))

    for cli_spec in (doc.service_clients or []):
        srv_type = import_ros_type(cli_spec.type)
        ident = service_to_identifier(cli_spec.name)
        attr = 'cli_' + ident + '_'
        setattr(node, attr, node.create_client(srv_type, cli_spec.name))
