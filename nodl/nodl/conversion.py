"""Convert rosgraph_msgs.msg.Node to a NoDL document."""

from __future__ import annotations

from rcl_interfaces.msg import ParameterType
from rcl_interfaces.msg import ParameterValue as RosParameterValue
from rclpy.qos import DurabilityPolicy, HistoryPolicy, LivelinessPolicy, ReliabilityPolicy

from nodl.models import (
    ActionEndpoint,
    NodlDocument,
    NodeMetadata,
    Parameter,
    QoS,
    ServiceEndpoint,
    TopicEndpoint,
)

# Maps rcl_interfaces ParameterType constant -> NoDL type string
_PARAM_TYPE_NAMES: dict[int, str | None] = {
    ParameterType.PARAMETER_NOT_SET: None,
    ParameterType.PARAMETER_BOOL: 'bool',
    ParameterType.PARAMETER_INTEGER: 'int',
    ParameterType.PARAMETER_DOUBLE: 'double',
    ParameterType.PARAMETER_STRING: 'string',
    ParameterType.PARAMETER_BYTE_ARRAY: 'byte_array',
    ParameterType.PARAMETER_BOOL_ARRAY: 'bool_array',
    ParameterType.PARAMETER_INTEGER_ARRAY: 'int_array',
    ParameterType.PARAMETER_DOUBLE_ARRAY: 'double_array',
    ParameterType.PARAMETER_STRING_ARRAY: 'string_array',
}

# Maps rcl_interfaces ParameterType constant -> ParameterValue attribute name
_PARAM_VALUE_FIELDS: dict[int, str] = {
    ParameterType.PARAMETER_BOOL: 'bool_value',
    ParameterType.PARAMETER_INTEGER: 'integer_value',
    ParameterType.PARAMETER_DOUBLE: 'double_value',
    ParameterType.PARAMETER_STRING: 'string_value',
    ParameterType.PARAMETER_BYTE_ARRAY: 'byte_array_value',
    ParameterType.PARAMETER_BOOL_ARRAY: 'bool_array_value',
    ParameterType.PARAMETER_INTEGER_ARRAY: 'integer_array_value',
    ParameterType.PARAMETER_DOUBLE_ARRAY: 'double_array_value',
    ParameterType.PARAMETER_STRING_ARRAY: 'string_array_value',
}

# Suffixes of services that every rclcpp/rclpy node automatically creates
_INTERNAL_PARAM_SERVICE_SUFFIXES = frozenset([
    'describe_parameters',
    'get_parameters',
    'get_parameter_types',
    'list_parameters',
    'set_parameters',
    'set_parameters_atomically',
])

# Topics automatically published by every rclcpp/rclpy node
_INTERNAL_TOPICS = frozenset([
    '/rosout',
    '/parameter_events',
])


_INT64_MAX = 2**63 - 1  # ROS uses this to represent "infinite" / no-deadline


def _duration_to_ms(duration) -> int | None:
    """Convert a builtin_interfaces/Duration to milliseconds.

    Returns None for both zero (unset) and INT64_MAX (ROS infinite sentinel).
    """
    total_ns = duration.sec * 1_000_000_000 + duration.nanosec
    if total_ns == 0 or total_ns >= _INT64_MAX:
        return None
    return total_ns // 1_000_000


def _qos_to_model(qos) -> QoS | None:
    """Convert a rosgraph_msgs.msg.QoSProfile to a QoS model, or None if indeterminate."""
    kwargs: dict = {}

    try:
        h = HistoryPolicy(qos.history)
        if h is HistoryPolicy.KEEP_LAST:
            kwargs['history'] = max(1, qos.depth)
        elif h is HistoryPolicy.KEEP_ALL:
            kwargs['history'] = 'ALL'
    except ValueError:
        pass

    try:
        r = ReliabilityPolicy(qos.reliability)
        if r in (ReliabilityPolicy.RELIABLE, ReliabilityPolicy.BEST_EFFORT):
            kwargs['reliability'] = r.name
    except ValueError:
        pass

    if 'history' not in kwargs or 'reliability' not in kwargs:
        return None

    try:
        d = DurabilityPolicy(qos.durability)
        if d in (DurabilityPolicy.TRANSIENT_LOCAL, DurabilityPolicy.VOLATILE):
            kwargs['durability'] = d.name
    except ValueError:
        pass

    deadline_ms = _duration_to_ms(qos.deadline)
    if deadline_ms is not None:
        kwargs['deadline_ms'] = deadline_ms

    lifespan_ms = _duration_to_ms(qos.lifespan)
    if lifespan_ms is not None:
        kwargs['lifespan_ms'] = lifespan_ms

    try:
        lv = LivelinessPolicy(qos.liveliness)
        if lv in (LivelinessPolicy.AUTOMATIC, LivelinessPolicy.MANUAL_BY_TOPIC):
            kwargs['liveliness'] = lv.name
    except ValueError:
        pass

    lease_ms = _duration_to_ms(qos.liveliness_lease_duration)
    if lease_ms is not None:
        kwargs['lease_duration_ms'] = lease_ms

    return QoS(**kwargs)


def _is_internal_service(name: str) -> bool:
    """Return True if the service name is an internal node service."""
    suffix = name.rsplit('/', 1)[-1]
    if suffix in _INTERNAL_PARAM_SERVICE_SUFFIXES:
        return True
    if '/_action/' in name:
        return True
    return False


def _is_internal_topic(name: str) -> bool:
    """Return True if the topic is an internal node topic."""
    if name in _INTERNAL_TOPICS:
        return True
    if '/_action/' in name:
        return True
    return False


def _parse_fqn(fqn: str) -> tuple[str, str]:
    """Split a fully-qualified node name into (namespace, short_name)."""
    idx = fqn.rfind('/')
    if idx <= 0:
        return '/', fqn.lstrip('/')
    return fqn[:idx], fqn[idx + 1:]


def _reconstruct_action_type(action_msg) -> str:
    """Extract the action type string from an Action.msg.

    The send_goal request type name is stored as the action type directly
    when produced by nodl.describe, or may have a '_SendGoal' suffix when
    produced by other tools.
    """
    type_name = action_msg.send_goal.request_type.name
    if type_name.endswith('_SendGoal'):
        return type_name[:-len('_SendGoal')]
    return type_name


def to_nodl(node_msg, *, assume_current_as_default: bool = False) -> NodlDocument:
    """Convert a rosgraph_msgs.msg.Node to a NodlDocument.

    assume_current_as_default: if True, treat current parameter values as
        the default_value field in the output.
    """
    namespace, name = _parse_fqn(node_msg.name)

    # Parameters
    param_map: dict[str, Parameter] = {}
    if node_msg.parameters:
        values_by_name: dict[str, object] = {}
        if (
            assume_current_as_default
            and node_msg.parameter_values
            and len(node_msg.parameter_values) == len(node_msg.parameters)
        ):
            for desc, val in zip(node_msg.parameters, node_msg.parameter_values):
                field = _PARAM_VALUE_FIELDS.get(val.type)
                if field:
                    values_by_name[desc.name] = getattr(val, field)

        for desc in node_msg.parameters:
            type_name = _PARAM_TYPE_NAMES.get(desc.type)
            if type_name is None:
                continue

            param_map[desc.name] = Parameter(
                type=type_name,
                description=desc.description or None,
                read_only=True if desc.read_only else None,
                additional_constraints=desc.additional_constraints or None,
                default_value=values_by_name.get(desc.name),
            )

    # Publishers
    publishers = [
        TopicEndpoint(
            topic=topic.name,
            type=topic.type.name,
            qos=_qos_to_model(topic.qos),
        )
        for topic in node_msg.publishers
        if not _is_internal_topic(topic.name)
    ]

    # Subscriptions
    subscriptions = [
        TopicEndpoint(
            topic=topic.name,
            type=topic.type.name,
            qos=_qos_to_model(topic.qos),
        )
        for topic in node_msg.subscriptions
        if not _is_internal_topic(topic.name)
    ]

    # Service servers
    service_servers = [
        ServiceEndpoint(name=srv.name, type=srv.request_type.name)
        for srv in node_msg.service_servers
        if not _is_internal_service(srv.name)
    ]

    # Service clients
    service_clients = [
        ServiceEndpoint(name=srv.name, type=srv.request_type.name)
        for srv in node_msg.service_clients
        if not _is_internal_service(srv.name)
    ]

    # Action servers
    action_servers = [
        ActionEndpoint(name=action.name, type=_reconstruct_action_type(action))
        for action in node_msg.action_servers
    ]

    # Action clients
    action_clients = [
        ActionEndpoint(name=action.name, type=_reconstruct_action_type(action))
        for action in node_msg.action_clients
    ]

    return NodlDocument(
        node=NodeMetadata(name=name, namespace=namespace),
        parameters=param_map or None,
        publishers=publishers or None,
        subscriptions=subscriptions or None,
        service_servers=service_servers or None,
        service_clients=service_clients or None,
        action_servers=action_servers or None,
        action_clients=action_clients or None,
    )
