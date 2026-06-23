# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0

import pytest

from ros2nodl.describe._transform import (
    is_hidden_parameter,
    is_hidden_publisher,
    is_hidden_service,
    is_hidden_subscription,
)


@pytest.mark.parametrize(
    'predicate,name,type',
    [
        (is_hidden_publisher, '/rosout', 'rcl_interfaces/msg/Log'),
        (is_hidden_publisher, '/parameter_events', 'rcl_interfaces/msg/ParameterEvent'),
        (is_hidden_subscription, '/parameter_events', 'rcl_interfaces/msg/ParameterEvent'),
        (is_hidden_service, '/n/get_parameters', 'rcl_interfaces/srv/GetParameters'),
        (is_hidden_service, '/n/set_parameters', 'rcl_interfaces/srv/SetParameters'),
        (
            is_hidden_service,
            '/n/get_type_description',
            'type_description_interfaces/srv/GetTypeDescription',
        ),
    ],
)
def test_framework_endpoints_are_hidden(predicate, name, type):
    assert predicate(name, type)
    assert not predicate(name, 'example_interfaces/msg/Other')


@pytest.mark.parametrize(
    'name,hidden',
    [
        ('use_sim_time', True),
        ('start_type_description_service', True),
        ('qos_overrides./scan.publisher.depth', True),
        ('user_parameter', False),
    ],
)
def test_framework_parameters(name, hidden):
    assert is_hidden_parameter(name) is hidden
