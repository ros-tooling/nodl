"""Unit tests for _support helpers — no rclpy required."""
import pytest

from nodl_rclpy._support import (
    import_ros_type,
    qos_from_spec,
    service_to_identifier,
    topic_to_identifier,
)
from nodl.models import QoS as NodlQoS


# ---------------------------------------------------------------------------
# topic_to_identifier / service_to_identifier
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('topic,expected', [
    ('/scan', 'scan'),
    ('/my/long/topic', 'my_long_topic'),
    ('relative', 'relative'),
    ('/a/b', 'a_b'),
])
def test_topic_to_identifier(topic, expected):
    assert topic_to_identifier(topic) == expected


@pytest.mark.parametrize('name,expected', [
    ('/set_bool', 'set_bool'),
    ('/robot/reset', 'robot_reset'),
    ('plain', 'plain'),
])
def test_service_to_identifier(name, expected):
    assert service_to_identifier(name) == expected


# ---------------------------------------------------------------------------
# qos_from_spec
# ---------------------------------------------------------------------------

def test_qos_default_when_none():
    qos = qos_from_spec(None)
    assert qos.depth == 10


def test_qos_reliable():
    from rclpy.qos import ReliabilityPolicy
    spec = NodlQoS(history=5, reliability='RELIABLE')
    qos = qos_from_spec(spec)
    assert qos.reliability == ReliabilityPolicy.RELIABLE
    assert qos.depth == 5


def test_qos_best_effort():
    from rclpy.qos import ReliabilityPolicy
    spec = NodlQoS(history=5, reliability='BEST_EFFORT')
    qos = qos_from_spec(spec)
    assert qos.reliability == ReliabilityPolicy.BEST_EFFORT


def test_qos_keep_all():
    from rclpy.qos import HistoryPolicy
    spec = NodlQoS(history='ALL', reliability='RELIABLE')
    qos = qos_from_spec(spec)
    assert qos.history == HistoryPolicy.KEEP_ALL


def test_qos_transient_local():
    from rclpy.qos import DurabilityPolicy
    spec = NodlQoS(history=10, reliability='RELIABLE', durability='TRANSIENT_LOCAL')
    qos = qos_from_spec(spec)
    assert qos.durability == DurabilityPolicy.TRANSIENT_LOCAL


# ---------------------------------------------------------------------------
# import_ros_type
# ---------------------------------------------------------------------------

def test_import_ros_type_msg():
    from std_msgs.msg import String
    assert import_ros_type('std_msgs/msg/String') is String


def test_import_ros_type_srv():
    from std_srvs.srv import SetBool
    assert import_ros_type('std_srvs/srv/SetBool') is SetBool


def test_import_ros_type_invalid_module():
    with pytest.raises(ImportError):
        import_ros_type('nonexistent_pkg/msg/Foo')


def test_import_ros_type_invalid_class():
    with pytest.raises(ImportError):
        import_ros_type('std_msgs/msg/NoSuchType')


def test_import_ros_type_bad_string():
    with pytest.raises(ValueError):
        import_ros_type('bare_name')
