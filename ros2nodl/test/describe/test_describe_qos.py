# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0

import pytest
import stub_msgs

from nodl_schema.models import Durability, History, Liveliness, Reliability
from ros2nodl.describe._transform import to_qos_profile


@pytest.mark.parametrize(
    'field,value,expected',
    [
        ('history', stub_msgs.HISTORY_KEEP_LAST, History.KEEP_LAST),
        ('history', stub_msgs.HISTORY_KEEP_ALL, History.KEEP_ALL),
        ('reliability', stub_msgs.RELIABILITY_RELIABLE, Reliability.RELIABLE),
        ('reliability', stub_msgs.RELIABILITY_BEST_EFFORT, Reliability.BEST_EFFORT),
        ('reliability', stub_msgs.RELIABILITY_BEST_AVAILABLE, Reliability.BEST_AVAILABLE),
        ('durability', stub_msgs.DURABILITY_TRANSIENT_LOCAL, Durability.TRANSIENT_LOCAL),
        ('durability', stub_msgs.DURABILITY_VOLATILE, Durability.VOLATILE),
        ('durability', stub_msgs.DURABILITY_BEST_AVAILABLE, Durability.BEST_AVAILABLE),
        ('liveliness', stub_msgs.LIVELINESS_AUTOMATIC, Liveliness.AUTOMATIC),
        ('liveliness', stub_msgs.LIVELINESS_MANUAL_BY_TOPIC, Liveliness.MANUAL_BY_TOPIC),
        ('liveliness', stub_msgs.LIVELINESS_BEST_AVAILABLE, Liveliness.BEST_AVAILABLE),
    ],
)
def test_policy_mapping(field, value, expected):
    output = to_qos_profile(stub_msgs.qos(**{field: value}, depth=1))
    assert getattr(output, field) is expected


def test_unknown_policy_handling():
    output = to_qos_profile(
        stub_msgs.qos(
            history=stub_msgs.HISTORY_UNKNOWN,
            reliability=stub_msgs.RELIABILITY_UNKNOWN,
            durability=stub_msgs.DURABILITY_UNKNOWN,
            liveliness=stub_msgs.LIVELINESS_UNKNOWN,
        )
    )
    assert output.history is History.SYSTEM_DEFAULT
    assert output.reliability is Reliability.SYSTEM_DEFAULT
    assert output.durability is None
    assert output.liveliness is None


def test_invalid_required_policy_records_gap():
    gaps = []
    output = to_qos_profile(stub_msgs.qos(history=99, reliability=99), gaps, 'publishers[0].qos')
    assert output.history is History.SYSTEM_DEFAULT
    assert output.reliability is Reliability.SYSTEM_DEFAULT
    assert [gap.path for gap in gaps] == [
        'publishers[0].qos.history',
        'publishers[0].qos.reliability',
    ]


def test_depth_only_applies_to_keep_last():
    assert to_qos_profile(stub_msgs.qos(history=stub_msgs.HISTORY_KEEP_LAST, depth=7)).depth == 7
    assert to_qos_profile(stub_msgs.qos(history=stub_msgs.HISTORY_KEEP_ALL, depth=7)).depth is None


def test_invalid_keep_last_depth_records_gap():
    gaps = []
    output = to_qos_profile(stub_msgs.qos(history=stub_msgs.HISTORY_KEEP_LAST), gaps, 'qos')
    assert output.depth is None
    assert gaps[0].path == 'qos.depth'


def test_duration_conversion_and_omission():
    output = to_qos_profile(
        stub_msgs.qos(
            deadline=(1, 500_000_000),
            lifespan=(0, 0),
            liveliness_lease=(stub_msgs.INT32_MAX, 0),
        )
    )
    assert output.deadline_ns == 1_500_000_000
    assert output.lifespan_ns is None
    assert output.liveliness_lease_duration_ns is None
