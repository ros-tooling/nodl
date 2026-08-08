# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0

import json

import stub_msgs

from nodl_schema import dump_nodl
from nodl_schema.validation import validate
from ros2nodl.describe import DescribeOptions, node_to_nodl


def _qos():
    return stub_msgs.qos(
        history=stub_msgs.HISTORY_KEEP_LAST,
        reliability=stub_msgs.RELIABILITY_RELIABLE,
        durability=stub_msgs.DURABILITY_VOLATILE,
        depth=10,
    )


def _node():
    return stub_msgs.node_msg(
        name='/robot/controller',
        publishers=[
            stub_msgs.topic('/state', 'std_msgs/msg/String', _qos()),
            stub_msgs.topic('/rosout', 'rcl_interfaces/msg/Log', _qos()),
        ],
        subscriptions=[stub_msgs.topic('/command', 'std_msgs/msg/String', _qos())],
        service_servers=[stub_msgs.service('/reset', 'std_srvs/srv/Empty')],
        service_clients=[stub_msgs.service('/calibrate', 'std_srvs/srv/Trigger')],
        action_servers=[
            stub_msgs.action(
                '/move',
                send_goal_type='example_interfaces/action/Fibonacci_SendGoal',
            )
        ],
        parameters=[
            stub_msgs.descriptor('speed', stub_msgs.PARAMETER_DOUBLE),
            stub_msgs.descriptor('use_sim_time', stub_msgs.PARAMETER_BOOL),
        ],
        parameter_values=[
            stub_msgs.value(stub_msgs.PARAMETER_DOUBLE, double_value=1.5),
            stub_msgs.value(stub_msgs.PARAMETER_BOOL, bool_value=False),
        ],
    )


def _data(result):
    return json.loads(dump_nodl(result.doc, format='json'))


def test_minimal_node_only_has_schema_version():
    assert _data(node_to_nodl(stub_msgs.node_msg())) == {'nodl_version': 2}


def test_complete_node_maps_filters_and_validates():
    result = node_to_nodl(_node())
    data = _data(result)
    validate(data)

    assert result.gaps == []
    assert 'name' not in data
    assert [endpoint['name'] for endpoint in data['publishers']] == ['/state']
    assert data['subscriptions'][0]['name'] == '/command'
    assert data['service_servers'][0]['type'] == 'std_srvs/srv/Empty'
    assert data['service_clients'][0]['type'] == 'std_srvs/srv/Trigger'
    assert data['action_servers'][0]['type'] == 'example_interfaces/action/Fibonacci'
    assert data['parameters']['speed']['default_value'] == 1.5
    assert 'use_sim_time' not in data['parameters']


def test_options_control_parameters_and_filtering():
    without_parameters = _data(node_to_nodl(_node(), DescribeOptions(include_parameters=False)))
    with_hidden = _data(node_to_nodl(_node(), DescribeOptions(keep_hidden=True)))
    assert 'parameters' not in without_parameters
    assert '/rosout' in [endpoint['name'] for endpoint in with_hidden['publishers']]
    assert 'use_sim_time' in with_hidden['parameters']


def test_identical_endpoints_are_deduplicated():
    topic = stub_msgs.topic('/state', 'std_msgs/msg/String', _qos())
    data = _data(node_to_nodl(stub_msgs.node_msg(publishers=[topic, topic])))
    assert len(data['publishers']) == 1
