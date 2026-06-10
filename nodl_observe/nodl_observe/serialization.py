# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Serializers for observed ``rosgraph_msgs/Node`` messages.

These are pure functions of a ROS message -- they do not import :mod:`rclpy`
and never touch the ROS graph.  They are the single rendering path shared by the
CLI verb (stdout + ``-o`` file dump) and the golden-file tests, so the bytes
produced here are the bytes those tests diff against.
"""

import json

from rosidl_runtime_py import message_to_yaml
from rosidl_runtime_py.convert import message_to_ordereddict


def to_yaml(msg) -> str:
    """Render a ROS message as YAML.

    This is the human-readable / stdout default and the golden-file format.
    """
    return message_to_yaml(msg)


def to_json(msg) -> str:
    """Render a ROS message as indented JSON with a trailing newline."""
    return json.dumps(message_to_ordereddict(msg), indent=2) + '\n'
