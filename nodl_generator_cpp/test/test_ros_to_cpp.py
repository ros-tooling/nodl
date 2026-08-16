# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0

from nodl_generator_cpp.ros_to_cpp import qos_to_cpp
from nodl_schema.models import Durability, History, Liveliness, QosProfile, Reliability


def _qos(**kwargs) -> QosProfile:
    """Build a QosProfile with KEEP_LAST / SYSTEM_DEFAULT defaults."""
    defaults = {'history': History.KEEP_LAST, 'reliability': Reliability.SYSTEM_DEFAULT}
    defaults.update(kwargs)
    return QosProfile(**defaults)


# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------


def test_keep_last():
    assert qos_to_cpp(_qos(depth=10)) == 'rclcpp::QoS(10)'


def test_keep_last_no_depth_defaults_to_10():
    assert qos_to_cpp(_qos()) == 'rclcpp::QoS(10)'


def test_keep_all():
    result = qos_to_cpp(_qos(history=History.KEEP_ALL))
    assert result == 'rclcpp::QoS(rclcpp::KeepAll())'


def test_system_default_history():
    assert qos_to_cpp(_qos(history=History.SYSTEM_DEFAULT)) == 'rclcpp::SystemDefaultsQoS()'


def test_system_default_history_with_overrides():
    result = qos_to_cpp(_qos(history=History.SYSTEM_DEFAULT, reliability=Reliability.RELIABLE))
    assert result == 'rclcpp::SystemDefaultsQoS().reliable()'


# ---------------------------------------------------------------------------
# Reliability
# ---------------------------------------------------------------------------


def test_reliable():
    assert qos_to_cpp(_qos(depth=1, reliability=Reliability.RELIABLE)) == 'rclcpp::QoS(1).reliable()'


def test_best_effort():
    assert qos_to_cpp(_qos(depth=1, reliability=Reliability.BEST_EFFORT)) == 'rclcpp::QoS(1).best_effort()'


def test_system_default_reliability_omitted():
    assert qos_to_cpp(_qos(depth=5)) == 'rclcpp::QoS(5)'


def test_best_available_reliability():
    result = qos_to_cpp(_qos(depth=1, reliability=Reliability.BEST_AVAILABLE))
    assert result == 'rclcpp::QoS(1).reliability(rclcpp::ReliabilityPolicy::BestAvailable)'


# ---------------------------------------------------------------------------
# Durability
# ---------------------------------------------------------------------------


def test_transient_local():
    result = qos_to_cpp(_qos(depth=1, durability=Durability.TRANSIENT_LOCAL))
    assert result == 'rclcpp::QoS(1).transient_local()'


def test_durability_volatile():
    result = qos_to_cpp(_qos(depth=1, durability=Durability.VOLATILE))
    assert result == 'rclcpp::QoS(1).durability_volatile()'


def test_system_default_durability_omitted():
    assert qos_to_cpp(_qos(depth=1, durability=Durability.SYSTEM_DEFAULT)) == 'rclcpp::QoS(1)'


def test_best_available_durability():
    result = qos_to_cpp(_qos(depth=1, durability=Durability.BEST_AVAILABLE))
    assert result == 'rclcpp::QoS(1).durability(rclcpp::DurabilityPolicy::BestAvailable)'


# ---------------------------------------------------------------------------
# Liveliness
# ---------------------------------------------------------------------------


def test_liveliness_automatic():
    result = qos_to_cpp(_qos(depth=1, liveliness=Liveliness.AUTOMATIC))
    assert result == 'rclcpp::QoS(1).liveliness(rclcpp::LivelinessPolicy::Automatic)'


def test_liveliness_manual_by_topic():
    result = qos_to_cpp(_qos(depth=1, liveliness=Liveliness.MANUAL_BY_TOPIC))
    assert result == 'rclcpp::QoS(1).liveliness(rclcpp::LivelinessPolicy::ManualByTopic)'


def test_system_default_liveliness_omitted():
    assert qos_to_cpp(_qos(depth=1, liveliness=Liveliness.SYSTEM_DEFAULT)) == 'rclcpp::QoS(1)'


def test_best_available_liveliness():
    result = qos_to_cpp(_qos(depth=1, liveliness=Liveliness.BEST_AVAILABLE))
    assert result == 'rclcpp::QoS(1).liveliness(rclcpp::LivelinessPolicy::BestAvailable)'


# ---------------------------------------------------------------------------
# Duration-based policies
# ---------------------------------------------------------------------------


def test_deadline():
    result = qos_to_cpp(_qos(depth=1, deadline_ns=1_000_000))
    assert result == 'rclcpp::QoS(1).deadline(rclcpp::Duration::from_nanoseconds(1000000))'


def test_lifespan():
    result = qos_to_cpp(_qos(depth=1, lifespan_ns=5_000_000_000))
    assert result == 'rclcpp::QoS(1).lifespan(rclcpp::Duration::from_nanoseconds(5000000000))'


def test_liveliness_lease_duration():
    result = qos_to_cpp(_qos(depth=1, liveliness_lease_duration_ns=2_000_000_000))
    assert result == ('rclcpp::QoS(1).liveliness_lease_duration(rclcpp::Duration::from_nanoseconds(2000000000))')


def test_zero_deadline_omitted():
    assert qos_to_cpp(_qos(depth=1, deadline_ns=0)) == 'rclcpp::QoS(1)'


def test_zero_lifespan_omitted():
    assert qos_to_cpp(_qos(depth=1, lifespan_ns=0)) == 'rclcpp::QoS(1)'


def test_zero_liveliness_lease_duration_omitted():
    assert qos_to_cpp(_qos(depth=1, liveliness_lease_duration_ns=0)) == 'rclcpp::QoS(1)'


# ---------------------------------------------------------------------------
# Combined
# ---------------------------------------------------------------------------


def test_all_fields():
    result = qos_to_cpp(
        _qos(
            depth=5,
            reliability=Reliability.RELIABLE,
            durability=Durability.TRANSIENT_LOCAL,
            liveliness=Liveliness.MANUAL_BY_TOPIC,
            deadline_ns=1_000_000,
            lifespan_ns=2_000_000,
            liveliness_lease_duration_ns=3_000_000,
        )
    )
    assert result == (
        'rclcpp::QoS(5)'
        '.reliable()'
        '.transient_local()'
        '.liveliness(rclcpp::LivelinessPolicy::ManualByTopic)'
        '.deadline(rclcpp::Duration::from_nanoseconds(1000000))'
        '.lifespan(rclcpp::Duration::from_nanoseconds(2000000))'
        '.liveliness_lease_duration(rclcpp::Duration::from_nanoseconds(3000000))'
    )
