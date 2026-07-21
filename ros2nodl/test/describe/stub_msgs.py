# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Small duck-typed message builders for ROS-free transform tests."""

from types import SimpleNamespace as NS

HISTORY_SYSTEM_DEFAULT, HISTORY_KEEP_LAST, HISTORY_KEEP_ALL, HISTORY_UNKNOWN = range(4)
(
    RELIABILITY_SYSTEM_DEFAULT,
    RELIABILITY_RELIABLE,
    RELIABILITY_BEST_EFFORT,
    RELIABILITY_UNKNOWN,
    RELIABILITY_BEST_AVAILABLE,
) = range(5)
(
    DURABILITY_SYSTEM_DEFAULT,
    DURABILITY_TRANSIENT_LOCAL,
    DURABILITY_VOLATILE,
    DURABILITY_UNKNOWN,
    DURABILITY_BEST_AVAILABLE,
) = range(5)
LIVELINESS_SYSTEM_DEFAULT = 0
LIVELINESS_AUTOMATIC = 1
LIVELINESS_MANUAL_BY_TOPIC = 3
LIVELINESS_UNKNOWN = 4
LIVELINESS_BEST_AVAILABLE = 5
INT32_MAX = 2_147_483_647
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


def duration(sec=INT32_MAX, nanosec=0):
    return NS(sec=sec, nanosec=nanosec)


def _duration(value):
    if value is None:
        return duration()
    return duration(*value) if isinstance(value, tuple) else value


def qos(
    history=HISTORY_SYSTEM_DEFAULT,
    reliability=RELIABILITY_SYSTEM_DEFAULT,
    durability=DURABILITY_SYSTEM_DEFAULT,
    liveliness=LIVELINESS_SYSTEM_DEFAULT,
    depth=0,
    deadline=None,
    lifespan=None,
    liveliness_lease=None,
):
    return NS(
        history=history,
        reliability=reliability,
        durability=durability,
        liveliness=liveliness,
        depth=depth,
        deadline=_duration(deadline),
        lifespan=_duration(lifespan),
        liveliness_lease_duration=_duration(liveliness_lease),
    )


def interface_type(name):
    return NS(name=name, hash=NS(version=1, value=list(range(32))))


def topic(name, type, qos=None):
    return NS(name=name, type=interface_type(type), qos=qos or globals()['qos']())


def service(name, request_type, response_type=None, request_qos=None, response_qos=None):
    unknown_qos = qos(reliability=RELIABILITY_UNKNOWN, durability=DURABILITY_UNKNOWN)
    return NS(
        name=name,
        request_type=interface_type(request_type),
        response_type=interface_type(response_type or request_type),
        request_qos=request_qos or unknown_qos,
        response_qos=response_qos or unknown_qos,
    )


def action(
    name,
    send_goal_type=None,
    get_result_type=None,
    cancel_goal_type='action_msgs/srv/CancelGoal',
    feedback_type=None,
    status_type='action_msgs/msg/GoalStatusArray',
):
    return NS(
        name=name,
        send_goal=service(f'{name}/_action/send_goal', send_goal_type) if send_goal_type else None,
        get_result=service(f'{name}/_action/get_result', get_result_type) if get_result_type else None,
        cancel_goal=service(f'{name}/_action/cancel_goal', cancel_goal_type),
        feedback=topic(f'{name}/_action/feedback', feedback_type) if feedback_type else None,
        status=topic(f'{name}/_action/status', status_type),
    )


def fp_range(from_value, to_value, step=0.0):
    return NS(from_value=from_value, to_value=to_value, step=step)


def int_range(from_value, to_value, step=0):
    return NS(from_value=from_value, to_value=to_value, step=step)


def descriptor(
    name,
    type,
    description='',
    additional_constraints='',
    read_only=False,
    dynamic_typing=False,
    floating_point_range=None,
    integer_range=None,
):
    return NS(
        name=name,
        type=type,
        description=description,
        additional_constraints=additional_constraints,
        read_only=read_only,
        dynamic_typing=dynamic_typing,
        floating_point_range=[] if floating_point_range is None else [floating_point_range],
        integer_range=[] if integer_range is None else [integer_range],
    )


def value(type, **fields):
    defaults = {
        'bool_value': False,
        'integer_value': 0,
        'double_value': 0.0,
        'string_value': '',
        'byte_array_value': [],
        'bool_array_value': [],
        'integer_array_value': [],
        'double_array_value': [],
        'string_array_value': [],
    }
    return NS(type=type, **(defaults | fields))


def node_msg(name='/n', **arrays):
    fields = {
        key: list(arrays.get(key, ()))
        for key in (
            'publishers',
            'subscriptions',
            'service_servers',
            'service_clients',
            'action_servers',
            'action_clients',
            'parameters',
            'parameter_values',
        )
    }
    return NS(name=name, **fields)
