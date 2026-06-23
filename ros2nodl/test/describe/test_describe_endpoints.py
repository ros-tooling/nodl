# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0

import pytest
import stub_msgs

from ros2nodl.describe._transform import action_endpoint, service_endpoint, topic_endpoint


def test_topic_maps_name_type_and_qos():
    endpoint = topic_endpoint(
        stub_msgs.topic(
            '/scan',
            'sensor_msgs/msg/LaserScan',
            stub_msgs.qos(history=stub_msgs.HISTORY_KEEP_LAST, depth=10),
        )
    )
    assert endpoint.name == '/scan'
    assert endpoint.type == 'sensor_msgs/msg/LaserScan'
    assert endpoint.qos.depth == 10
    assert 'hash' not in endpoint.dict()


def test_service_uses_request_type_and_omits_qos():
    endpoint = service_endpoint(stub_msgs.service('/reset', 'std_srvs/srv/Empty'))
    assert endpoint.type == 'std_srvs/srv/Empty'
    assert endpoint.qos is None


@pytest.mark.parametrize(
    'kwargs',
    [
        {'send_goal_type': 'example_interfaces/action/Fibonacci_SendGoal'},
        {'get_result_type': 'example_interfaces/action/Fibonacci_GetResult'},
        {'send_goal_type': 'example_interfaces/action/Fibonacci'},
    ],
)
def test_action_type_recovery(kwargs):
    endpoint = action_endpoint(stub_msgs.action('/fibonacci', **kwargs))
    assert endpoint.type == 'example_interfaces/action/Fibonacci'


def test_missing_action_type_becomes_a_gap():
    gaps = []
    endpoint = action_endpoint(stub_msgs.action('/fibonacci'), gaps, 'action_servers[0]')
    assert endpoint.type == ''
    assert gaps[0].path == 'action_servers[0].type'


@pytest.mark.parametrize(
    'mapper,message',
    [
        (topic_endpoint, stub_msgs.topic('/scan', '')),
        (service_endpoint, stub_msgs.service('/reset', '')),
    ],
)
def test_invalid_endpoint_type_becomes_a_gap(mapper, message):
    gaps = []
    mapper(message, gaps, 'endpoints[0]')
    assert gaps[0].path == 'endpoints[0].type'
