# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Convert ROS-domain values to C++ representations.

Pure functions that translate ROS interface types, QoS profiles, and
names into the C++ strings needed by the Jinja2 templates.
"""

from __future__ import annotations

import re

from nodl_schema.models import Durability, History, Liveliness, QosProfile, Reliability

# ---------------------------------------------------------------------------
# CamelCase → snake_case
# ---------------------------------------------------------------------------

_CAMEL_RE1 = re.compile(r'([A-Z]+)([A-Z][a-z])')
_CAMEL_RE2 = re.compile(r'([a-z0-9])([A-Z])')


def _camel_to_snake(name: str) -> str:
    """Convert a CamelCase name to snake_case.

    >>> _camel_to_snake('NavigateToPose')
    'navigate_to_pose'
    >>> _camel_to_snake('SetBool')
    'set_bool'
    """
    s = _CAMEL_RE1.sub(r'\1_\2', name)
    return _CAMEL_RE2.sub(r'\1_\2', s).lower()


# ---------------------------------------------------------------------------
# ROS type conversions
# ---------------------------------------------------------------------------


def ros_type_to_cpp(ros_type: str) -> str:
    """Convert a ROS interface type to its C++ namespace equivalent.

    >>> ros_type_to_cpp('std_msgs/msg/String')
    'std_msgs::msg::String'
    >>> ros_type_to_cpp('nav2_msgs/action/NavigateToPose')
    'nav2_msgs::action::NavigateToPose'
    """
    return ros_type.replace('/', '::')


def ros_type_to_header(ros_type: str) -> str:
    """Convert a ROS interface type to its C++ header include path.

    >>> ros_type_to_header('std_msgs/msg/String')
    'std_msgs/msg/string.hpp'
    >>> ros_type_to_header('nav2_msgs/action/NavigateToPose')
    'nav2_msgs/action/navigate_to_pose.hpp'
    """
    prefix, type_name = ros_type.rsplit('/', 1)
    return f'{prefix}/{_camel_to_snake(type_name)}.hpp'


# ---------------------------------------------------------------------------
# QoS
# ---------------------------------------------------------------------------


def qos_to_cpp(qos: QosProfile) -> str:
    """Convert a QoS profile to an ``rclcpp::QoS`` constructor expression.

    Handles all QoS fields: history, depth, reliability, durability,
    liveliness, deadline, lifespan, and liveliness lease duration.
    ``SYSTEM_DEFAULT`` values are omitted (already the default for
    both ``rclcpp::QoS(depth)`` and ``rclcpp::SystemDefaultsQoS()``).

    >>> from nodl_schema.models import History, Reliability, QosProfile
    >>> qos_to_cpp(QosProfile(history=History.KEEP_LAST, depth=10, reliability=Reliability.RELIABLE))
    'rclcpp::QoS(10).reliable()'
    >>> qos_to_cpp(QosProfile(history=History.KEEP_LAST, depth=1, reliability=Reliability.BEST_EFFORT))
    'rclcpp::QoS(1).best_effort()'
    """
    # -- Base expression from history --
    if qos.history is History.KEEP_ALL:
        expr = 'rclcpp::QoS(rclcpp::KeepAll())'
    elif qos.history is History.SYSTEM_DEFAULT:
        expr = 'rclcpp::SystemDefaultsQoS()'
    else:  # KEEP_LAST
        depth = qos.depth if qos.depth is not None else 10
        expr = f'rclcpp::QoS({depth})'

    # -- Reliability --
    if qos.reliability is Reliability.RELIABLE:
        expr += '.reliable()'
    elif qos.reliability is Reliability.BEST_EFFORT:
        expr += '.best_effort()'
    elif qos.reliability is Reliability.BEST_AVAILABLE:
        expr += '.reliability(rclcpp::ReliabilityPolicy::BestAvailable)'
    # SYSTEM_DEFAULT: omit (already the default)

    # -- Durability --
    if qos.durability is not None and qos.durability is not Durability.SYSTEM_DEFAULT:
        if qos.durability is Durability.TRANSIENT_LOCAL:
            expr += '.transient_local()'
        elif qos.durability is Durability.VOLATILE:
            expr += '.durability_volatile()'
        elif qos.durability is Durability.BEST_AVAILABLE:
            expr += '.durability(rclcpp::DurabilityPolicy::BestAvailable)'

    # -- Liveliness --
    if qos.liveliness is not None and qos.liveliness is not Liveliness.SYSTEM_DEFAULT:
        if qos.liveliness is Liveliness.AUTOMATIC:
            expr += '.liveliness(rclcpp::LivelinessPolicy::Automatic)'
        elif qos.liveliness is Liveliness.MANUAL_BY_TOPIC:
            expr += '.liveliness(rclcpp::LivelinessPolicy::ManualByTopic)'
        elif qos.liveliness is Liveliness.BEST_AVAILABLE:
            expr += '.liveliness(rclcpp::LivelinessPolicy::BestAvailable)'

    # -- Duration-based policies (zero means disabled / infinite) --
    if qos.deadline_ns is not None and qos.deadline_ns > 0:
        expr += f'.deadline(rclcpp::Duration::from_nanoseconds({qos.deadline_ns}))'

    if qos.lifespan_ns is not None and qos.lifespan_ns > 0:
        expr += f'.lifespan(rclcpp::Duration::from_nanoseconds({qos.lifespan_ns}))'

    if qos.liveliness_lease_duration_ns is not None and qos.liveliness_lease_duration_ns > 0:
        expr += f'.liveliness_lease_duration(rclcpp::Duration::from_nanoseconds({qos.liveliness_lease_duration_ns}))'

    return expr


# ---------------------------------------------------------------------------
# Naming
# ---------------------------------------------------------------------------


def to_class_name(target_name: str) -> str:
    """Convert a snake_case target name to PascalCase with a ``Base`` suffix.

    >>> to_class_name('my_node')
    'MyNodeBase'
    >>> to_class_name('laser_scanner')
    'LaserScannerBase'
    """
    return ''.join(word.capitalize() for word in target_name.split('_')) + 'Base'


def to_member_name(name: str) -> str:
    """Sanitise a ROS entity name for use as a C++ identifier fragment.

    Strips leading ``~/`` or ``/``, replaces remaining ``/`` with ``_``.

    >>> to_member_name('/rosout')
    'rosout'
    >>> to_member_name('~/describe_parameters')
    'describe_parameters'
    >>> to_member_name('cmd_vel')
    'cmd_vel'
    """
    name = name.removeprefix('~/').lstrip('/')
    return name.replace('/', '_')
