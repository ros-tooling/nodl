# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0

from nodl_schema.models import (
    History,
    NodlDocument,
    ParameterDefinition,
    QosProfile,
    Reliability,
    ScalarType,
    ServiceEndpoint,
    TopicEndpoint,
)
from ros2nodl.infrastructure import strip_infrastructure

_QOS = QosProfile(history=History.KEEP_LAST, depth=1, reliability=Reliability.RELIABLE)


def _topic(name: str, type: str) -> TopicEndpoint:
    return TopicEndpoint(name=name, type=type, qos=_QOS)


def _document() -> NodlDocument:
    return NodlDocument(
        nodl_version=2,
        publishers=[
            _topic('/rosout', 'rcl_interfaces/msg/Log'),
            _topic('/parameter_events', 'rcl_interfaces/msg/ParameterEvent'),
            _topic('/scan', 'sensor_msgs/msg/LaserScan'),
        ],
        service_servers=[
            ServiceEndpoint(name='~/get_parameters', type='rcl_interfaces/srv/GetParameters'),
            ServiceEndpoint(name='~/set_parameters', type='rcl_interfaces/srv/SetParameters'),
            ServiceEndpoint(name='/reset', type='std_srvs/srv/Empty'),
        ],
        parameters={
            'use_sim_time': ParameterDefinition(type=ScalarType.bool, default_value=False),
            'qos_overrides./scan.publisher.depth': ParameterDefinition(type=ScalarType.int),
            'frame_id': ParameterDefinition(type=ScalarType.string),
        },
    )


def test_strip_removes_framework_endpoints_and_parameters():
    stripped = strip_infrastructure(_document())

    assert stripped.publishers is not None
    assert stripped.service_servers is not None
    assert stripped.parameters is not None
    assert [pub.name for pub in stripped.publishers] == ['/scan']
    assert [srv.name for srv in stripped.service_servers] == ['/reset']
    assert list(stripped.parameters) == ['frame_id']


def test_strip_is_idempotent():
    once = strip_infrastructure(_document())
    twice = strip_infrastructure(once)

    assert twice == once


def test_strip_collapses_empty_sections_to_none():
    doc = NodlDocument(
        nodl_version=2,
        publishers=[_topic('/rosout', 'rcl_interfaces/msg/Log')],
        parameters={'use_sim_time': ParameterDefinition(type=ScalarType.bool)},
    )

    stripped = strip_infrastructure(doc)

    assert stripped.publishers is None
    assert stripped.parameters is None


def test_strip_keeps_user_endpoint_with_colliding_name():
    doc = NodlDocument(
        nodl_version=2,
        publishers=[_topic('/rosout', 'example_interfaces/msg/Other')],
    )

    stripped = strip_infrastructure(doc)

    assert stripped.publishers is not None
    assert [pub.name for pub in stripped.publishers] == ['/rosout']
