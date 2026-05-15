"""Internal helpers: topic/service identifiers, QoS conversion, dynamic type import."""
from __future__ import annotations

import importlib
from typing import Optional

from rclpy.qos import (
    DurabilityPolicy,
    HistoryPolicy,
    QoSProfile,
    ReliabilityPolicy,
)

from nodl.models import QoS as NodlQoS


def topic_to_identifier(topic: str) -> str:
    """'/my/long/topic' -> 'my_long_topic'"""
    return topic.lstrip('/').replace('/', '_')


def service_to_identifier(name: str) -> str:
    """'/my/service' -> 'my_service'"""
    return name.lstrip('/').replace('/', '_')


def qos_from_spec(qos: Optional[NodlQoS]) -> QoSProfile:
    if qos is None:
        return QoSProfile(depth=10)

    if qos.history == 'ALL':
        history = HistoryPolicy.KEEP_ALL
        depth = 0
    else:
        history = HistoryPolicy.KEEP_LAST
        depth = int(qos.history)

    reliability = (
        ReliabilityPolicy.RELIABLE
        if qos.reliability == 'RELIABLE'
        else ReliabilityPolicy.BEST_EFFORT
    )
    durability = (
        DurabilityPolicy.TRANSIENT_LOCAL
        if qos.durability == 'TRANSIENT_LOCAL'
        else DurabilityPolicy.VOLATILE
    )

    return QoSProfile(
        history=history,
        depth=depth,
        reliability=reliability,
        durability=durability,
    )


def import_ros_type(ros_type: str):
    """Import a ROS message/service type from a slash-separated string.

    'std_msgs/msg/String' -> std_msgs.msg.String
    """
    parts = ros_type.split('/')
    if len(parts) < 2:
        raise ValueError(f'Invalid ROS type string: {ros_type!r}')
    module_path = '.'.join(parts[:-1])
    class_name = parts[-1]
    try:
        module = importlib.import_module(module_path)
    except ModuleNotFoundError as exc:
        raise ImportError(f'Cannot import ROS type {ros_type!r}: {exc}') from exc
    try:
        return getattr(module, class_name)
    except AttributeError as exc:
        raise ImportError(
            f'Type {class_name!r} not found in module {module_path!r}'
        ) from exc
