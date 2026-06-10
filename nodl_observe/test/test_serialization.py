# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Tests for the pure serialization module (no ROS executor)."""

import json

import pytest

# Guard: skip if rosgraph_msgs predates 2.0.4 (no Node.msg) or is absent --
# importing nodl_observe exercises both.
pytest.importorskip('nodl_observe')

from rosgraph_msgs.msg import Node as NodeMsg, Topic  # noqa: E402

from nodl_observe.serialization import to_json, to_yaml  # noqa: E402


def _sample_node():
    msg = NodeMsg()
    msg.name = '/ns/talker'
    topic = Topic()
    topic.name = '/chatter'
    topic.type.name = 'std_msgs/msg/String'
    msg.publishers = [topic]
    return msg


def test_to_yaml_is_string_with_fields():
    out = to_yaml(_sample_node())
    assert isinstance(out, str)
    assert 'name: /ns/talker' in out
    assert 'std_msgs/msg/String' in out


def test_to_json_is_indented_with_trailing_newline():
    out = to_json(_sample_node())
    assert out.endswith('\n')
    # indent=2 -> the second line is indented two spaces.
    assert out.splitlines()[1].startswith('  ')
    parsed = json.loads(out)
    assert parsed['name'] == '/ns/talker'
    assert parsed['publishers'][0]['name'] == '/chatter'


def test_json_round_trips_through_parser():
    out = to_json(_sample_node())
    # Valid JSON regardless of field ordering.
    json.loads(out)
