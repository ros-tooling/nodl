# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Layer-1 unit tests for nodl_observe (no ROS executor, no spinning nodes).

These feed the pure builder functions hand-rolled ``TopicEndpointInfo`` /
parameter fixtures and assert exact ``Node`` sub-message contents.  Every
assertion traces to a failure mode of the observer (QoS mistranslation, missed
endpoint kind, bad action folding, non-deterministic ordering, parameter
timeout handling) -- not to re-testing rclpy's graph API.
"""

import pytest

# Guard: skip if the ROS stack is absent or its rosgraph_msgs predates 2.0.4
# (no Node.msg) -- importing nodl_observe exercises both.
pytest.importorskip('rclpy')
pytest.importorskip('nodl_observe')

from rcl_interfaces.msg import ParameterDescriptor, ParameterValue  # noqa: E402
from rclpy.duration import Duration  # noqa: E402
from rclpy.qos import (  # noqa: E402
    DurabilityPolicy,
    HistoryPolicy,
    LivelinessPolicy,
    QoSProfile,
    ReliabilityPolicy,
)
from rclpy.type_hash import TypeHash as RclTypeHash  # noqa: E402
from rosgraph_msgs.msg import QoSProfile as QoSProfileMsg  # noqa: E402

from nodl_observe import _split_fqn  # noqa: E402
from nodl_observe._endpoints import (  # noqa: E402
    build_service_endpoints,
    build_topic_endpoints,
    fold_actions,
)
from nodl_observe._parameters import build_parameters, collect_parameters  # noqa: E402
from nodl_observe._qos import qos_to_msg, unknown_qos_msg  # noqa: E402


# --------------------------------------------------------------------------- #
# Fixtures / fakes
# --------------------------------------------------------------------------- #


class FakeEndpointInfo:
    """Stand-in for rclpy's ``TopicEndpointInfo`` for the pure builders."""

    def __init__(self, topic_type, qos_profile, *, type_hash=None,
                 node_name='target', node_namespace='/'):
        self.topic_type = topic_type
        self.qos_profile = qos_profile
        self.topic_type_hash = type_hash if type_hash is not None else RclTypeHash()
        self.node_name = node_name
        self.node_namespace = node_namespace


def _hash(byte_value):
    h = RclTypeHash()
    h.version = 1
    h.value = bytes([byte_value] * 32)
    return h


# --------------------------------------------------------------------------- #
# QoS mapping
# --------------------------------------------------------------------------- #


class TestQoSMapping:
    @pytest.mark.parametrize('policy,expected', [
        (HistoryPolicy.SYSTEM_DEFAULT, QoSProfileMsg.HISTORY_SYSTEM_DEFAULT),
        (HistoryPolicy.KEEP_LAST, QoSProfileMsg.HISTORY_KEEP_LAST),
        (HistoryPolicy.KEEP_ALL, QoSProfileMsg.HISTORY_KEEP_ALL),
        (HistoryPolicy.UNKNOWN, QoSProfileMsg.HISTORY_UNKNOWN),
    ])
    def test_history_enum(self, policy, expected):
        qos = QoSProfile(depth=1, history=policy)
        assert qos_to_msg(qos).history == expected

    @pytest.mark.parametrize('policy,expected', [
        (ReliabilityPolicy.SYSTEM_DEFAULT, QoSProfileMsg.RELIABILITY_SYSTEM_DEFAULT),
        (ReliabilityPolicy.RELIABLE, QoSProfileMsg.RELIABILITY_RELIABLE),
        (ReliabilityPolicy.BEST_EFFORT, QoSProfileMsg.RELIABILITY_BEST_EFFORT),
        (ReliabilityPolicy.UNKNOWN, QoSProfileMsg.RELIABILITY_UNKNOWN),
        (ReliabilityPolicy.BEST_AVAILABLE, QoSProfileMsg.RELIABILITY_BEST_AVAILABLE),
    ])
    def test_reliability_enum(self, policy, expected):
        qos = QoSProfile(depth=1, reliability=policy)
        assert qos_to_msg(qos).reliability == expected

    @pytest.mark.parametrize('policy,expected', [
        (DurabilityPolicy.SYSTEM_DEFAULT, QoSProfileMsg.DURABILITY_SYSTEM_DEFAULT),
        (DurabilityPolicy.TRANSIENT_LOCAL, QoSProfileMsg.DURABILITY_TRANSIENT_LOCAL),
        (DurabilityPolicy.VOLATILE, QoSProfileMsg.DURABILITY_VOLATILE),
        (DurabilityPolicy.UNKNOWN, QoSProfileMsg.DURABILITY_UNKNOWN),
        (DurabilityPolicy.BEST_AVAILABLE, QoSProfileMsg.DURABILITY_BEST_AVAILABLE),
    ])
    def test_durability_enum(self, policy, expected):
        qos = QoSProfile(depth=1, durability=policy)
        assert qos_to_msg(qos).durability == expected

    @pytest.mark.parametrize('policy,expected', [
        (LivelinessPolicy.SYSTEM_DEFAULT, QoSProfileMsg.LIVELINESS_SYSTEM_DEFAULT),
        (LivelinessPolicy.AUTOMATIC, QoSProfileMsg.LIVELINESS_AUTOMATIC),
        (LivelinessPolicy.MANUAL_BY_TOPIC, QoSProfileMsg.LIVELINESS_MANUAL_BY_TOPIC),
        (LivelinessPolicy.UNKNOWN, QoSProfileMsg.LIVELINESS_UNKNOWN),
        (LivelinessPolicy.BEST_AVAILABLE, QoSProfileMsg.LIVELINESS_BEST_AVAILABLE),
    ])
    def test_liveliness_enum(self, policy, expected):
        qos = QoSProfile(depth=1, liveliness=policy)
        assert qos_to_msg(qos).liveliness == expected

    def test_depth_and_durations_carried(self):
        qos = QoSProfile(
            depth=7,
            deadline=Duration(seconds=1, nanoseconds=500),
            lifespan=Duration(seconds=2),
            liveliness_lease_duration=Duration(seconds=3, nanoseconds=4),
        )
        msg = qos_to_msg(qos)
        assert msg.depth == 7
        assert (msg.deadline.sec, msg.deadline.nanosec) == (1, 500)
        assert (msg.lifespan.sec, msg.lifespan.nanosec) == (2, 0)
        assert (msg.liveliness_lease_duration.sec,
                msg.liveliness_lease_duration.nanosec) == (3, 4)

    def test_observed_qos_never_system_default_for_explicit(self):
        # An *observed* policy of SYSTEM_DEFAULT/BEST_AVAILABLE indicates a
        # mapping bug.  With a concrete RELIABLE/VOLATILE profile, the output
        # must be concrete too -- never a request-time placeholder.
        qos = QoSProfile(
            depth=1,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.VOLATILE,
            liveliness=LivelinessPolicy.AUTOMATIC,
            history=HistoryPolicy.KEEP_LAST,
        )
        msg = qos_to_msg(qos)
        assert msg.reliability not in (
            QoSProfileMsg.RELIABILITY_SYSTEM_DEFAULT,
            QoSProfileMsg.RELIABILITY_BEST_AVAILABLE,
        )
        assert msg.durability not in (
            QoSProfileMsg.DURABILITY_SYSTEM_DEFAULT,
            QoSProfileMsg.DURABILITY_BEST_AVAILABLE,
        )

    def test_unknown_qos_msg_all_unknown(self):
        msg = unknown_qos_msg()
        assert msg.history == QoSProfileMsg.HISTORY_UNKNOWN
        assert msg.reliability == QoSProfileMsg.RELIABILITY_UNKNOWN
        assert msg.durability == QoSProfileMsg.DURABILITY_UNKNOWN
        assert msg.liveliness == QoSProfileMsg.LIVELINESS_UNKNOWN


# --------------------------------------------------------------------------- #
# Topic endpoints (QoS + type hash)
# --------------------------------------------------------------------------- #


class TestTopicEndpoints:
    def test_topic_carries_type_hash_and_qos(self):
        info = FakeEndpointInfo(
            'std_msgs/msg/String',
            QoSProfile(depth=10, reliability=ReliabilityPolicy.BEST_EFFORT),
            type_hash=_hash(0xAB),
        )
        topics = build_topic_endpoints([('/chatter', ['std_msgs/msg/String'])],
                                       {'/chatter': [info]})
        assert len(topics) == 1
        t = topics[0]
        assert t.name == '/chatter'
        assert t.type.name == 'std_msgs/msg/String'
        assert t.type.hash.version == 1
        assert list(t.type.hash.value) == [0xAB] * 32
        assert t.qos.reliability == QoSProfileMsg.RELIABILITY_BEST_EFFORT
        assert t.qos.depth == 10

    def test_topic_without_info_is_name_type_only(self):
        # No introspection info -> still emit the endpoint (never drop it).
        topics = build_topic_endpoints([('/chatter', ['std_msgs/msg/String'])], {})
        assert len(topics) == 1
        assert topics[0].name == '/chatter'
        assert topics[0].type.name == 'std_msgs/msg/String'
        assert topics[0].qos.depth == 0

    def test_topics_sorted_by_name_then_type(self):
        infos = {
            '/b': [FakeEndpointInfo('t/B', QoSProfile(depth=1))],
            '/a': [FakeEndpointInfo('t/A', QoSProfile(depth=1))],
        }
        topics = build_topic_endpoints(
            [('/b', ['t/B']), ('/a', ['t/A'])], infos)
        assert [t.name for t in topics] == ['/a', '/b']


# --------------------------------------------------------------------------- #
# Service endpoints (UNKNOWN QoS, no type hash)
# --------------------------------------------------------------------------- #


class TestServiceEndpoints:
    def test_service_has_unknown_qos_and_no_hash(self):
        services = build_service_endpoints(
            [('/add', ['example_interfaces/srv/AddTwoInts'])])
        assert len(services) == 1
        s = services[0]
        assert s.name == '/add'
        assert s.request_type.name == 'example_interfaces/srv/AddTwoInts'
        assert s.response_type.name == 'example_interfaces/srv/AddTwoInts'
        # Type hash unset -> message default (version 1 per TypeHash.msg) with
        # an all-zero value, i.e. no real hash was recorded.
        assert list(s.request_type.hash.value) == [0] * 32
        assert s.request_qos.reliability == QoSProfileMsg.RELIABILITY_UNKNOWN
        assert s.response_qos.durability == QoSProfileMsg.DURABILITY_UNKNOWN

    def test_services_sorted(self):
        services = build_service_endpoints(
            [('/z', ['t/Z']), ('/a', ['t/A'])])
        assert [s.name for s in services] == ['/a', '/z']


# --------------------------------------------------------------------------- #
# Action folding
# --------------------------------------------------------------------------- #


def _action_service(name):
    return (name, ['t/Srv'])


class TestActionFolding:
    def _full_constituents(self, action='/fib'):
        services = build_service_endpoints([
            (action + '/_action/send_goal', ['t/SendGoal']),
            (action + '/_action/get_result', ['t/GetResult']),
            (action + '/_action/cancel_goal', ['t/CancelGoal']),
            ('/other_service', ['t/Other']),
        ])
        topics = build_topic_endpoints([
            (action + '/_action/feedback', ['t/Feedback']),
            (action + '/_action/status', ['t/Status']),
            ('/other_topic', ['t/OtherTopic']),
        ], {})
        return services, topics

    def test_constituents_folded_and_removed_from_flat(self):
        services, topics = self._full_constituents('/fib')
        actions = fold_actions(
            [('/fib', ['action_tutorials_interfaces/action/Fibonacci'])],
            services, topics)
        assert len(actions) == 1
        a = actions[0]
        assert a.name == '/fib'
        assert a.send_goal.name == '/fib/_action/send_goal'
        assert a.get_result.name == '/fib/_action/get_result'
        assert a.cancel_goal.name == '/fib/_action/cancel_goal'
        assert a.feedback.name == '/fib/_action/feedback'
        assert a.status.name == '/fib/_action/status'
        # Folded constituents must NOT remain flat.
        assert [s.name for s in services] == ['/other_service']
        assert [t.name for t in topics] == ['/other_topic']
        # Folded services keep UNKNOWN QoS.
        assert a.send_goal.request_qos.reliability == QoSProfileMsg.RELIABILITY_UNKNOWN

    def test_orphan_action_entity_stays_flat(self):
        # An `_action/*` service whose parent action is NOT in the action graph
        # must be left flat, never silently discarded.
        services = build_service_endpoints([
            ('/ghost/_action/send_goal', ['t/SendGoal']),
        ])
        topics = []
        actions = fold_actions([], services, topics)  # no actions in graph
        assert actions == []
        assert [s.name for s in services] == ['/ghost/_action/send_goal']

    def test_partial_action_uses_placeholders(self):
        # If only some constituents are present, the action is still well-formed
        # (placeholders fill the gaps) and present ones are consumed.
        services = build_service_endpoints([
            ('/fib/_action/send_goal', ['t/SendGoal']),
        ])
        topics = build_topic_endpoints([
            ('/fib/_action/feedback', ['t/Feedback']),
        ], {})
        actions = fold_actions([('/fib', ['t/Action'])], services, topics)
        assert len(actions) == 1
        a = actions[0]
        assert a.send_goal.name == '/fib/_action/send_goal'
        # Missing constituents get placeholder names.
        assert a.get_result.name == '/fib/_action/get_result'
        assert a.status.name == '/fib/_action/status'
        assert services == []
        assert topics == []

    def test_actions_sorted(self):
        services = build_service_endpoints([])
        topics = []
        actions = fold_actions(
            [('/z', ['t/Z']), ('/a', ['t/A'])], services, topics)
        assert [a.name for a in actions] == ['/a', '/z']


# --------------------------------------------------------------------------- #
# Parameter pairing / degradation
# --------------------------------------------------------------------------- #


def _descriptor(name, read_only=False):
    d = ParameterDescriptor()
    d.name = name
    d.read_only = read_only
    return d


def _value(integer):
    v = ParameterValue()
    v.type = ParameterValue.PARAMETER_INTEGER if hasattr(
        ParameterValue, 'PARAMETER_INTEGER') else 2
    v.integer_value = integer
    return v


class TestParameterPairing:
    def test_paired_and_sorted_by_name(self):
        names = ['z_param', 'a_param']
        descriptors = [_descriptor('z_param'), _descriptor('a_param', read_only=True)]
        values = [_value(1), _value(2)]
        out_d, out_v = build_parameters(names, descriptors, values)
        assert [d.name for d in out_d] == ['a_param', 'z_param']
        # Values stay matched 1:1 with their descriptor after sorting.
        assert out_v[0].integer_value == 2  # a_param
        assert out_v[1].integer_value == 1  # z_param
        assert out_d[0].read_only is True

    def test_length_mismatch_keeps_only_complete_pairs(self):
        names = ['a', 'b']
        descriptors = [_descriptor('a')]  # 'b' described away mid-observation
        values = [_value(1), _value(2)]
        out_d, out_v = build_parameters(names, descriptors, values)
        assert [d.name for d in out_d] == ['a']
        assert len(out_v) == 1

    def test_empty_inputs(self):
        out_d, out_v = build_parameters([], [], [])
        assert out_d == []
        assert out_v == []


# --------------------------------------------------------------------------- #
# Parameter collection degradation (graceful, no executor needed)
# --------------------------------------------------------------------------- #


class _FakeLogger:
    def __init__(self):
        self.warnings = []

    def warning(self, msg):
        self.warnings.append(msg)


class _FakeClient:
    def __init__(self, ready):
        self._ready = ready
        self.destroyed = False

    def service_is_ready(self):
        return self._ready

    def wait_for_service(self, timeout_sec=None):
        return self._ready


class _FakeNode:
    """Minimal node fake exercising the degradation path without spinning."""

    def __init__(self, services_ready):
        self._services_ready = services_ready
        self._logger = _FakeLogger()
        self.clients = []

    def get_logger(self):
        return self._logger

    def create_client(self, srv_type, name):
        client = _FakeClient(self._services_ready)
        self.clients.append(client)
        return client

    def destroy_client(self, client):
        client.destroyed = True


class TestParameterDegradation:
    def test_unresponsive_target_returns_empty_with_warning(self):
        node = _FakeNode(services_ready=False)
        descriptors, values = collect_parameters(node, '/target', timeout_sec=0.01)
        assert descriptors == []
        assert values == []
        assert node.get_logger().warnings, 'expected a degradation warning'
        # All created clients must be cleaned up even on the failure path.
        assert all(c.destroyed for c in node.clients)


# --------------------------------------------------------------------------- #
# FQN splitting
# --------------------------------------------------------------------------- #


class TestSplitFqn:
    @pytest.mark.parametrize('fqn,expected', [
        ('/talker', ('talker', '/')),
        ('/ns/talker', ('talker', '/ns')),
        ('/ns/sub/talker', ('talker', '/ns/sub')),
        ('/ns/talker/', ('talker', '/ns')),
    ])
    def test_split(self, fqn, expected):
        assert _split_fqn(fqn) == expected
