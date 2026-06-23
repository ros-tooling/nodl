# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Pure, duck-typed ``rosgraph_msgs/Node`` to NoDL transform."""

from __future__ import annotations

from typing import Any, Callable, Optional

from nodl_schema.models import (
    ActionEndpoint,
    ArrayType,
    Durability,
    History,
    Liveliness,
    NodlDocument,
    ParameterDefinition,
    QosProfile,
    Reliability,
    ScalarType,
    ServiceEndpoint,
    TopicEndpoint,
    Validation,
)
from ros2nodl.describe import DescribeOptions, DescribeResult


def _record(gaps: Optional[list], path: str, reason: str) -> None:
    if gaps is not None:
        from ros2nodl.describe import Gap

        gaps.append(Gap(path, reason))


# rosgraph_msgs/msg/QoSProfile constants. UNKNOWN required policies fall back to
# SYSTEM_DEFAULT; optional UNKNOWN policies are omitted.
_HISTORY_SYSTEM_DEFAULT, _HISTORY_KEEP_LAST, _HISTORY_KEEP_ALL, _HISTORY_UNKNOWN = range(4)
(
    _RELIABILITY_SYSTEM_DEFAULT,
    _RELIABILITY_RELIABLE,
    _RELIABILITY_BEST_EFFORT,
    _RELIABILITY_UNKNOWN,
    _RELIABILITY_BEST_AVAILABLE,
) = range(5)
(
    _DURABILITY_SYSTEM_DEFAULT,
    _DURABILITY_TRANSIENT_LOCAL,
    _DURABILITY_VOLATILE,
    _DURABILITY_UNKNOWN,
    _DURABILITY_BEST_AVAILABLE,
) = range(5)
_LIVELINESS_SYSTEM_DEFAULT = 0
_LIVELINESS_AUTOMATIC = 1
_LIVELINESS_MANUAL_BY_TOPIC = 3
_LIVELINESS_UNKNOWN = 4
_LIVELINESS_BEST_AVAILABLE = 5

_HISTORY_MAP = {
    _HISTORY_SYSTEM_DEFAULT: History.SYSTEM_DEFAULT,
    _HISTORY_KEEP_LAST: History.KEEP_LAST,
    _HISTORY_KEEP_ALL: History.KEEP_ALL,
    _HISTORY_UNKNOWN: History.SYSTEM_DEFAULT,
}
_RELIABILITY_MAP = {
    _RELIABILITY_SYSTEM_DEFAULT: Reliability.SYSTEM_DEFAULT,
    _RELIABILITY_RELIABLE: Reliability.RELIABLE,
    _RELIABILITY_BEST_EFFORT: Reliability.BEST_EFFORT,
    _RELIABILITY_UNKNOWN: Reliability.SYSTEM_DEFAULT,
    _RELIABILITY_BEST_AVAILABLE: Reliability.BEST_AVAILABLE,
}
_DURABILITY_MAP = {
    _DURABILITY_SYSTEM_DEFAULT: Durability.SYSTEM_DEFAULT,
    _DURABILITY_TRANSIENT_LOCAL: Durability.TRANSIENT_LOCAL,
    _DURABILITY_VOLATILE: Durability.VOLATILE,
    _DURABILITY_UNKNOWN: None,
    _DURABILITY_BEST_AVAILABLE: Durability.BEST_AVAILABLE,
}
_LIVELINESS_MAP = {
    _LIVELINESS_SYSTEM_DEFAULT: Liveliness.SYSTEM_DEFAULT,
    _LIVELINESS_AUTOMATIC: Liveliness.AUTOMATIC,
    _LIVELINESS_MANUAL_BY_TOPIC: Liveliness.MANUAL_BY_TOPIC,
    _LIVELINESS_UNKNOWN: None,
    _LIVELINESS_BEST_AVAILABLE: Liveliness.BEST_AVAILABLE,
}
_INT32_MAX = 2_147_483_647
_NS_PER_SEC = 1_000_000_000


def _duration_to_ns(duration) -> Optional[int]:
    if duration is None:
        return None
    sec = int(getattr(duration, 'sec', 0))
    nanosec = int(getattr(duration, 'nanosec', 0))
    if sec < 0 or sec == _INT32_MAX or (sec == 0 and nanosec == 0):
        return None
    return sec * _NS_PER_SEC + nanosec


def _required_policy(mapping, raw: int, fallback, gaps: Optional[list], path: str):
    value = mapping.get(raw)
    if value is not None:
        return value
    _record(gaps, path, f'unrecognised policy {raw}; using SYSTEM_DEFAULT')
    return fallback


def to_qos_profile(qos, gaps: Optional[list] = None, path: str = '') -> QosProfile:
    history_raw = int(getattr(qos, 'history', _HISTORY_SYSTEM_DEFAULT))
    reliability_raw = int(getattr(qos, 'reliability', _RELIABILITY_SYSTEM_DEFAULT))
    history = _required_policy(_HISTORY_MAP, history_raw, History.SYSTEM_DEFAULT, gaps, f'{path}.history')
    reliability = _required_policy(
        _RELIABILITY_MAP,
        reliability_raw,
        Reliability.SYSTEM_DEFAULT,
        gaps,
        f'{path}.reliability',
    )

    depth = None
    if history is History.KEEP_LAST:
        depth = int(getattr(qos, 'depth', 0))
        if depth < 1:
            _record(gaps, f'{path}.depth', f'KEEP_LAST requires depth >= 1, got {depth}')
            depth = None

    return QosProfile(
        history=history,
        depth=depth,
        reliability=reliability,
        durability=_DURABILITY_MAP.get(int(getattr(qos, 'durability', 0))),
        deadline_ns=_duration_to_ns(getattr(qos, 'deadline', None)),
        lifespan_ns=_duration_to_ns(getattr(qos, 'lifespan', None)),
        liveliness=_LIVELINESS_MAP.get(int(getattr(qos, 'liveliness', 0))),
        liveliness_lease_duration_ns=_duration_to_ns(getattr(qos, 'liveliness_lease_duration', None)),
    )


# Framework-created endpoints are matched by both name tail and type so user
# endpoints with a colliding name survive.
_HIDDEN_PUBLISHERS = {
    ('rosout', 'rcl_interfaces/msg/Log'),
    ('parameter_events', 'rcl_interfaces/msg/ParameterEvent'),
}
_HIDDEN_SUBSCRIPTIONS = {
    ('parameter_events', 'rcl_interfaces/msg/ParameterEvent'),
}
_HIDDEN_SERVICES = {
    ('describe_parameters', 'rcl_interfaces/srv/DescribeParameters'),
    ('get_parameter_types', 'rcl_interfaces/srv/GetParameterTypes'),
    ('get_parameters', 'rcl_interfaces/srv/GetParameters'),
    ('list_parameters', 'rcl_interfaces/srv/ListParameters'),
    ('set_parameters', 'rcl_interfaces/srv/SetParameters'),
    ('set_parameters_atomically', 'rcl_interfaces/srv/SetParametersAtomically'),
    ('get_type_description', 'type_description_interfaces/srv/GetTypeDescription'),
}
_HIDDEN_PARAMETERS = {'use_sim_time', 'start_type_description_service'}


def name_tail(name: str) -> str:
    return name.rsplit('/', 1)[-1]


def is_hidden_publisher(name: str, type: str) -> bool:
    return (name_tail(name), type) in _HIDDEN_PUBLISHERS


def is_hidden_subscription(name: str, type: str) -> bool:
    return (name_tail(name), type) in _HIDDEN_SUBSCRIPTIONS


def is_hidden_service(name: str, type: str) -> bool:
    return (name_tail(name), type) in _HIDDEN_SERVICES


def is_hidden_parameter(name: str) -> bool:
    return name in _HIDDEN_PARAMETERS or name.startswith('qos_overrides.')


def _build_endpoint(model, gaps: Optional[list], path: str, **fields):
    try:
        return model(**fields)
    except Exception as exc:
        reported = False
        for error in getattr(exc, 'errors', lambda: [])():
            field = error.get('loc', ('endpoint',))[0]
            if field in ('name', 'type'):
                _record(gaps, f'{path}.{field}', error.get('msg', 'invalid value'))
                reported = True
        if not reported:
            _record(gaps, path, str(exc))
        return model.construct(**fields)


def topic_endpoint(topic, gaps: Optional[list] = None, path: str = '') -> TopicEndpoint:
    return _build_endpoint(
        TopicEndpoint,
        gaps,
        path,
        name=getattr(topic, 'name', ''),
        type=getattr(getattr(topic, 'type', None), 'name', ''),
        qos=to_qos_profile(getattr(topic, 'qos', None), gaps, f'{path}.qos'),
    )


def service_endpoint(service, gaps: Optional[list] = None, path: str = '') -> ServiceEndpoint:
    return _build_endpoint(
        ServiceEndpoint,
        gaps,
        path,
        name=getattr(service, 'name', ''),
        type=getattr(getattr(service, 'request_type', None), 'name', ''),
        qos=None,
    )


def action_endpoint(action, gaps: Optional[list] = None, path: str = '') -> ActionEndpoint:
    send_goal = getattr(getattr(getattr(action, 'send_goal', None), 'request_type', None), 'name', '')
    get_result = getattr(getattr(getattr(action, 'get_result', None), 'request_type', None), 'name', '')
    action_type = send_goal or get_result
    for candidate, suffix in ((send_goal, '_SendGoal'), (get_result, '_GetResult')):
        if candidate and candidate.endswith(suffix) and len(candidate) > len(suffix):
            action_type = candidate[: -len(suffix)]
            break
    return _build_endpoint(
        ActionEndpoint,
        gaps,
        path,
        name=getattr(action, 'name', ''),
        type=action_type,
    )


# rcl_interfaces/msg/ParameterType constants.
(
    PARAMETER_NOT_SET,
    PARAMETER_BOOL,
    PARAMETER_INTEGER,
    PARAMETER_DOUBLE,
    PARAMETER_STRING,
    PARAMETER_BYTE_ARRAY,
    PARAMETER_BOOL_ARRAY,
    PARAMETER_INTEGER_ARRAY,
    PARAMETER_DOUBLE_ARRAY,
    PARAMETER_STRING_ARRAY,
) = range(10)

_TYPE_MAP: dict[int, Any] = {
    PARAMETER_BOOL: ScalarType.bool,
    PARAMETER_INTEGER: ScalarType.int,
    PARAMETER_DOUBLE: ScalarType.double,
    PARAMETER_STRING: ScalarType.string,
    PARAMETER_BYTE_ARRAY: ScalarType.none,
    PARAMETER_BOOL_ARRAY: ArrayType.bool_array,
    PARAMETER_INTEGER_ARRAY: ArrayType.int_array,
    PARAMETER_DOUBLE_ARRAY: ArrayType.double_array,
    PARAMETER_STRING_ARRAY: ArrayType.string_array,
}
_VALUE_FIELDS = {
    PARAMETER_BOOL: 'bool_value',
    PARAMETER_INTEGER: 'integer_value',
    PARAMETER_DOUBLE: 'double_value',
    PARAMETER_STRING: 'string_value',
    PARAMETER_BOOL_ARRAY: 'bool_array_value',
    PARAMETER_INTEGER_ARRAY: 'integer_array_value',
    PARAMETER_DOUBLE_ARRAY: 'double_array_value',
    PARAMETER_STRING_ARRAY: 'string_array_value',
}
_ARRAY_TYPES = {
    PARAMETER_BOOL_ARRAY,
    PARAMETER_INTEGER_ARRAY,
    PARAMETER_DOUBLE_ARRAY,
    PARAMETER_STRING_ARRAY,
}


def _resolved_parameter_type(descriptor, value) -> int:
    declared = int(descriptor.type)
    if declared == PARAMETER_NOT_SET and value is not None:
        return int(value.type)
    return declared


def _parameter_value(value, resolved_type: int):
    if value is None or int(value.type) != resolved_type:
        return None
    field = _VALUE_FIELDS.get(resolved_type)
    if field is None:
        return None
    result = getattr(value, field)
    return list(result) if resolved_type in _ARRAY_TYPES else result


def _parameter_validation(descriptor) -> Optional[Validation]:
    ranges = getattr(descriptor, 'floating_point_range', None) or getattr(descriptor, 'integer_range', None)
    if not ranges:
        return None
    return Validation(bounds=[ranges[0].from_value, ranges[0].to_value])


def parameter_definition(descriptor, value=None) -> ParameterDefinition:
    resolved_type = _resolved_parameter_type(descriptor, value)
    return ParameterDefinition(
        type=_TYPE_MAP.get(resolved_type, ScalarType.none),
        default_value=_parameter_value(value, resolved_type),
        description=descriptor.description,
        read_only=descriptor.read_only,
        additional_constraints=descriptor.additional_constraints,
        validation=_parameter_validation(descriptor),
    )


def _dedupe(endpoints: list) -> list:
    seen = set()
    result = []
    for endpoint in endpoints:
        key = endpoint.json(exclude_none=True)
        if key not in seen:
            seen.add(key)
            result.append(endpoint)
    return result


def _map_endpoints(
    items,
    mapper,
    gaps: list,
    array_name: str,
    hidden: Optional[Callable[[str, str], bool]] = None,
    keep_hidden: bool = False,
) -> list:
    result = []
    for index, item in enumerate(items or []):
        endpoint = mapper(item, gaps, f'{array_name}[{index}]')
        if hidden and not keep_hidden and hidden(endpoint.name, endpoint.type):
            continue
        result.append(endpoint)
    return _dedupe(result)


def _map_parameters(node, keep_hidden: bool) -> dict:
    values = list(getattr(node, 'parameter_values', None) or [])
    result = {}
    for index, descriptor in enumerate(getattr(node, 'parameters', None) or []):
        if keep_hidden or not is_hidden_parameter(descriptor.name):
            value = values[index] if index < len(values) else None
            result[descriptor.name] = parameter_definition(descriptor, value)
    return result


def convert(node, opts: Optional[DescribeOptions] = None) -> DescribeResult:
    opts = opts or DescribeOptions()
    gaps = []
    mapping = {
        'publishers': (topic_endpoint, is_hidden_publisher),
        'subscriptions': (topic_endpoint, is_hidden_subscription),
        'service_servers': (service_endpoint, is_hidden_service),
        'service_clients': (service_endpoint, is_hidden_service),
        'action_servers': (action_endpoint, None),
        'action_clients': (action_endpoint, None),
    }
    fields = {
        name: _map_endpoints(getattr(node, name, None), mapper, gaps, name, hidden, opts.keep_hidden) or None
        for name, (mapper, hidden) in mapping.items()
    }
    parameters = _map_parameters(node, opts.keep_hidden) if opts.include_parameters else {}
    doc = NodlDocument(nodl_version=2, parameters=parameters or None, **fields)
    return DescribeResult(doc=doc, gaps=gaps)
