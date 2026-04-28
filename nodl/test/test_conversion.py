"""Unit tests for NoDL Node.msg conversion.

Uses lightweight dataclass mocks so no ROS environment is required.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

import pytest

from nodl.conversion import (
    _duration_to_ns,
    _is_internal_service,
    _is_internal_topic,
    _parse_fqn,
    _qos_to_model,
    _reconstruct_action_type,
    to_nodl,
)
from nodl.models import NodlDocument


# ---------------------------------------------------------------------------
# Minimal message mocks
# ---------------------------------------------------------------------------

@dataclass
class Duration:
    sec: int = 0
    nanosec: int = 0


@dataclass
class QoSProfile:
    depth: int = 10
    history: int = 1          # KEEP_LAST
    reliability: int = 1      # RELIABLE
    durability: int = 2       # VOLATILE
    liveliness: int = 1       # AUTOMATIC
    deadline: Duration = field(default_factory=Duration)
    lifespan: Duration = field(default_factory=Duration)
    liveliness_lease_duration: Duration = field(default_factory=Duration)


@dataclass
class InterfaceType:
    name: str = ''


@dataclass
class Topic:
    name: str = ''
    type: InterfaceType = field(default_factory=InterfaceType)
    qos: QoSProfile = field(default_factory=QoSProfile)


@dataclass
class Service:
    name: str = ''
    request_type: InterfaceType = field(default_factory=InterfaceType)
    response_type: InterfaceType = field(default_factory=InterfaceType)
    request_qos: QoSProfile = field(default_factory=QoSProfile)
    response_qos: QoSProfile = field(default_factory=QoSProfile)


@dataclass
class Action:
    name: str = ''
    send_goal: Service = field(default_factory=Service)
    get_result: Service = field(default_factory=Service)
    cancel_goal: Service = field(default_factory=Service)
    feedback: Topic = field(default_factory=Topic)
    status: Topic = field(default_factory=Topic)


@dataclass
class ParameterDescriptor:
    name: str = ''
    type: int = 0
    description: str = ''
    additional_constraints: str = ''
    read_only: bool = False
    dynamic_typing: bool = False


@dataclass
class ParameterValue:
    type: int = 0
    bool_value: bool = False
    integer_value: int = 0
    double_value: float = 0.0
    string_value: str = ''
    byte_array_value: List[int] = field(default_factory=list)
    bool_array_value: List[bool] = field(default_factory=list)
    integer_array_value: List[int] = field(default_factory=list)
    double_array_value: List[float] = field(default_factory=list)
    string_array_value: List[str] = field(default_factory=list)


@dataclass
class NodeMsg:
    name: str = '/test_node'
    parameters: List[ParameterDescriptor] = field(default_factory=list)
    parameter_values: List[ParameterValue] = field(default_factory=list)
    publishers: List[Topic] = field(default_factory=list)
    subscriptions: List[Topic] = field(default_factory=list)
    service_servers: List[Service] = field(default_factory=list)
    service_clients: List[Service] = field(default_factory=list)
    action_servers: List[Action] = field(default_factory=list)
    action_clients: List[Action] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Helper tests
# ---------------------------------------------------------------------------

def test_parse_fqn_with_namespace():
    assert _parse_fqn('/my_ns/my_node') == ('/my_ns', 'my_node')


def test_parse_fqn_root_namespace():
    assert _parse_fqn('/my_node') == ('/', 'my_node')


def test_parse_fqn_deep_namespace():
    assert _parse_fqn('/a/b/c/node') == ('/a/b/c', 'node')


def test_is_internal_service_param_services():
    for suffix in ['list_parameters', 'get_parameters', 'set_parameters',
                   'describe_parameters', 'get_parameter_types', 'set_parameters_atomically']:
        assert _is_internal_service(f'/my_node/{suffix}')


def test_is_internal_service_action():
    assert _is_internal_service('/my_node/_action/send_goal')
    assert _is_internal_service('/my_node/_action/cancel_goal')
    assert _is_internal_service('/my_node/_action/get_result')


def test_is_internal_service_user_service():
    assert not _is_internal_service('/my_node/do_thing')


def test_is_internal_topic_rosout():
    assert _is_internal_topic('/rosout')


def test_is_internal_topic_parameter_events():
    assert _is_internal_topic('/parameter_events')


def test_is_internal_topic_action():
    assert _is_internal_topic('/my_node/_action/feedback')
    assert _is_internal_topic('/my_node/_action/status')


def test_is_internal_topic_user_topic():
    assert not _is_internal_topic('/chatter')
    assert not _is_internal_topic('/my_ns/image')


# ---------------------------------------------------------------------------
# QoS conversion
# ---------------------------------------------------------------------------

def test_qos_keep_last():
    qos = QoSProfile(depth=10, history=1)
    result = _qos_to_model(qos)
    assert result.history == 'KEEP_LAST'
    assert result.depth == 10


def test_qos_keep_all():
    qos = QoSProfile(history=2)
    result = _qos_to_model(qos)
    assert result.history == 'KEEP_ALL'


def test_qos_reliable():
    qos = QoSProfile(reliability=1)
    result = _qos_to_model(qos)
    assert result.reliability == 'RELIABLE'


def test_qos_best_effort():
    qos = QoSProfile(reliability=2)
    result = _qos_to_model(qos)
    assert result.reliability == 'BEST_EFFORT'


def test_qos_transient_local():
    qos = QoSProfile(durability=1)
    result = _qos_to_model(qos)
    assert result.durability == 'TRANSIENT_LOCAL'


def test_qos_volatile():
    qos = QoSProfile(durability=2)
    result = _qos_to_model(qos)
    assert result.durability == 'VOLATILE'


def test_qos_deadline_ns():
    qos = QoSProfile(deadline=Duration(sec=0, nanosec=100_000_000))  # 100ms
    result = _qos_to_model(qos)
    assert result.deadline_ns == 100_000_000


def test_qos_zero_duration_omitted():
    qos = QoSProfile(deadline=Duration(sec=0, nanosec=0))
    result = _qos_to_model(qos)
    assert result.deadline_ns is None


def test_qos_infinite_duration_omitted():
    int64_max_ns = 2**63 - 1
    sec = int64_max_ns // 1_000_000_000
    nanosec = int64_max_ns % 1_000_000_000
    qos = QoSProfile(deadline=Duration(sec=sec, nanosec=nanosec))
    result = _qos_to_model(qos)
    assert result.deadline_ns is None


def test_qos_unknown_history_uses_system_default():
    qos = QoSProfile(history=0)  # SYSTEM_DEFAULT
    result = _qos_to_model(qos)
    assert result.history == 'SYSTEM_DEFAULT'


def test_qos_unknown_reliability_uses_system_default():
    qos = QoSProfile(reliability=0)  # SYSTEM_DEFAULT
    result = _qos_to_model(qos)
    assert result.reliability == 'SYSTEM_DEFAULT'


def test_qos_liveliness_automatic():
    qos = QoSProfile(liveliness=1)
    result = _qos_to_model(qos)
    assert result.liveliness == 'AUTOMATIC'


def test_qos_liveliness_manual_by_topic():
    qos = QoSProfile(liveliness=3)
    result = _qos_to_model(qos)
    assert result.liveliness == 'MANUAL_BY_TOPIC'


# ---------------------------------------------------------------------------
# Action type reconstruction
# ---------------------------------------------------------------------------

def test_reconstruct_action_type_direct():
    action = Action(
        name='/navigate',
        send_goal=Service(request_type=InterfaceType(name='nav2_msgs/action/NavigateToPose')),
    )
    assert _reconstruct_action_type(action) == 'nav2_msgs/action/NavigateToPose'


def test_reconstruct_action_type_with_send_goal_suffix():
    action = Action(
        name='/navigate',
        send_goal=Service(request_type=InterfaceType(name='nav2_msgs/action/NavigateToPose_SendGoal')),
    )
    assert _reconstruct_action_type(action) == 'nav2_msgs/action/NavigateToPose'


# ---------------------------------------------------------------------------
# to_nodl
# ---------------------------------------------------------------------------

def test_empty_node():
    msg = NodeMsg(name='/my_node')
    result = to_nodl(msg)
    assert isinstance(result, NodlDocument)
    assert result.nodl_version == 2
    assert result.publishers is None
    assert result.parameters is None


def test_internal_topics_filtered():
    msg = NodeMsg(
        name='/node',
        publishers=[
            Topic(name='/rosout', type=InterfaceType('rcl_interfaces/msg/Log')),
            Topic(name='/parameter_events', type=InterfaceType('rcl_interfaces/msg/ParameterEvent')),
            Topic(name='/chatter', type=InterfaceType('std_msgs/msg/String')),
        ],
    )
    result = to_nodl(msg)
    assert len(result.publishers) == 1
    assert result.publishers[0].name == '/chatter'


def test_internal_services_filtered():
    msg = NodeMsg(
        name='/node',
        service_servers=[
            Service(name='/node/list_parameters',
                    request_type=InterfaceType('rcl_interfaces/srv/ListParameters')),
            Service(name='/node/describe_parameters',
                    request_type=InterfaceType('rcl_interfaces/srv/DescribeParameters')),
            Service(name='/reset', request_type=InterfaceType('std_srvs/srv/Trigger')),
        ],
    )
    result = to_nodl(msg)
    assert len(result.service_servers) == 1
    assert result.service_servers[0].name == '/reset'


def test_action_internal_services_filtered():
    msg = NodeMsg(
        name='/node',
        service_servers=[
            Service(name='/navigate/_action/send_goal',
                    request_type=InterfaceType('nav2_msgs/action/NavigateToPose')),
            Service(name='/navigate/_action/cancel_goal',
                    request_type=InterfaceType('action_msgs/srv/CancelGoal')),
        ],
    )
    result = to_nodl(msg)
    assert result.service_servers is None


def test_publisher_with_qos():
    qos = QoSProfile(depth=5, history=1, reliability=1, durability=1)
    msg = NodeMsg(
        name='/node',
        publishers=[
            Topic(name='/cmd_vel', type=InterfaceType('geometry_msgs/msg/Twist'), qos=qos),
        ],
    )
    result = to_nodl(msg)
    pub = result.publishers[0]
    assert pub.name == '/cmd_vel'
    assert pub.type == 'geometry_msgs/msg/Twist'
    assert pub.qos.history == 'KEEP_LAST'
    assert pub.qos.depth == 5
    assert pub.qos.reliability == 'RELIABLE'
    assert pub.qos.durability == 'TRANSIENT_LOCAL'


def test_subscription():
    msg = NodeMsg(
        name='/node',
        subscriptions=[
            Topic(name='/odom', type=InterfaceType('nav_msgs/msg/Odometry')),
        ],
    )
    result = to_nodl(msg)
    assert result.subscriptions[0].name == '/odom'


def test_parameters_basic_types():
    descriptors = [
        ParameterDescriptor(name='flag', type=1),         # bool
        ParameterDescriptor(name='count', type=2),        # int
        ParameterDescriptor(name='speed', type=3),        # double
        ParameterDescriptor(name='label', type=4),        # string
        ParameterDescriptor(name='raw', type=5),          # byte_array — skipped (unsupported)
    ]
    msg = NodeMsg(name='/node', parameters=descriptors)
    result = to_nodl(msg)
    assert result.parameters['flag'].type == 'bool'
    assert result.parameters['count'].type == 'int'
    assert result.parameters['speed'].type == 'double'
    assert result.parameters['label'].type == 'string'
    assert 'raw' not in result.parameters


def test_parameter_not_set_skipped():
    descriptors = [
        ParameterDescriptor(name='unset', type=0),  # NOT_SET
        ParameterDescriptor(name='flag', type=1),   # bool
    ]
    msg = NodeMsg(name='/node', parameters=descriptors)
    result = to_nodl(msg)
    assert 'unset' not in result.parameters
    assert 'flag' in result.parameters


def test_parameter_with_description_and_read_only():
    desc = ParameterDescriptor(name='max_vel', type=3, description='Max velocity', read_only=True)
    msg = NodeMsg(name='/node', parameters=[desc])
    result = to_nodl(msg)
    p = result.parameters['max_vel']
    assert p.description == 'Max velocity'
    assert p.read_only is True


def test_parameter_read_only_false_omitted():
    desc = ParameterDescriptor(name='p', type=4, read_only=False)
    msg = NodeMsg(name='/node', parameters=[desc])
    result = to_nodl(msg)
    assert result.parameters['p'].read_only is None


def test_parameter_assume_current_as_default():
    desc = ParameterDescriptor(name='speed', type=3)  # double
    val = ParameterValue(type=3, double_value=2.5)
    msg = NodeMsg(name='/node', parameters=[desc], parameter_values=[val])
    result = to_nodl(msg, assume_current_as_default=True)
    assert result.parameters['speed'].default_value == 2.5


def test_parameter_values_not_used_by_default():
    desc = ParameterDescriptor(name='speed', type=3)
    val = ParameterValue(type=3, double_value=2.5)
    msg = NodeMsg(name='/node', parameters=[desc], parameter_values=[val])
    result = to_nodl(msg)
    assert result.parameters['speed'].default_value is None


def test_parameter_values_ignored_if_size_mismatch():
    desc = ParameterDescriptor(name='speed', type=3)
    msg = NodeMsg(name='/node', parameters=[desc], parameter_values=[])
    result = to_nodl(msg, assume_current_as_default=True)
    assert result.parameters['speed'].default_value is None


def test_service_client():
    msg = NodeMsg(
        name='/node',
        service_clients=[
            Service(name='/remote_trigger', request_type=InterfaceType('std_srvs/srv/Trigger')),
        ],
    )
    result = to_nodl(msg)
    assert result.service_clients[0].name == '/remote_trigger'
    assert result.service_clients[0].type == 'std_srvs/srv/Trigger'


def test_action_server():
    action = Action(
        name='/navigate',
        send_goal=Service(request_type=InterfaceType(name='nav2_msgs/action/NavigateToPose')),
    )
    msg = NodeMsg(name='/node', action_servers=[action])
    result = to_nodl(msg)
    assert result.action_servers[0].name == '/navigate'
    assert result.action_servers[0].type == 'nav2_msgs/action/NavigateToPose'


def test_action_client():
    action = Action(
        name='/compute',
        send_goal=Service(request_type=InterfaceType(name='example_interfaces/action/Fibonacci')),
    )
    msg = NodeMsg(name='/node', action_clients=[action])
    result = to_nodl(msg)
    assert result.action_clients[0].name == '/compute'
    assert result.action_clients[0].type == 'example_interfaces/action/Fibonacci'


def test_empty_sections_omitted():
    msg = NodeMsg(name='/node')
    result = to_nodl(msg)
    for attr in ['publishers', 'subscriptions', 'service_servers',
                 'service_clients', 'action_servers', 'action_clients', 'parameters']:
        assert getattr(result, attr) is None


def test_to_nodl_output_is_valid_nodl():
    from nodl.schema import validate

    qos = QoSProfile(depth=10, history=1, reliability=1)
    msg = NodeMsg(
        name='/ns/my_node',
        parameters=[
            ParameterDescriptor(name='speed', type=3, description='Speed param'),
        ],
        publishers=[
            Topic(name='/cmd_vel', type=InterfaceType('geometry_msgs/msg/Twist'), qos=qos),
        ],
        subscriptions=[
            Topic(name='/odom', type=InterfaceType('nav_msgs/msg/Odometry'), qos=qos),
        ],
        service_servers=[
            Service(name='/reset', request_type=InterfaceType('std_srvs/srv/Trigger')),
        ],
        action_servers=[
            Action(
                name='/navigate',
                send_goal=Service(request_type=InterfaceType('nav2_msgs/action/NavigateToPose')),
            )
        ],
    )
    result = to_nodl(msg)
    assert isinstance(result, NodlDocument)
    validate(result.to_dict())  # Must not raise


def test_to_dict_excludes_none_fields():
    msg = NodeMsg(name='/node', parameters=[ParameterDescriptor(name='p', type=4)])
    result = to_nodl(msg)
    d = result.to_dict()
    # read_only was not set (None), so must not appear in dict
    assert 'read_only' not in d['parameters']['p']
