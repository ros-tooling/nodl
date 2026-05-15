"""Integration tests for nodl.describe using live rclpy nodes.

These tests require a working ROS 2 environment and are skipped otherwise.
"""

from __future__ import annotations

import threading
import time

import pytest

try:
    import rclpy
    import rclpy.executors
    from rclpy.node import Node
    _RCLPY_AVAILABLE = True
except ImportError:
    _RCLPY_AVAILABLE = False

pytestmark = pytest.mark.skipif(
    not _RCLPY_AVAILABLE, reason='rclpy not available'
)


class _SpinThread:
    """Context manager that spins an rclpy node in a background thread."""

    def __init__(self, node):
        self._node = node
        self._executor = rclpy.executors.SingleThreadedExecutor()
        self._executor.add_node(node)
        self._thread = threading.Thread(target=self._executor.spin, daemon=True)

    def __enter__(self):
        self._thread.start()
        return self

    def __exit__(self, *_):
        self._executor.shutdown(timeout_sec=1.0)


@pytest.fixture(scope='module')
def ros_context():
    """Initialize rclpy once for the module and tear it down after."""
    rclpy.init()
    yield
    rclpy.shutdown()


@pytest.fixture
def talker_node(ros_context):
    """Create a simple node with a publisher and a subscription."""
    from std_msgs.msg import String
    node = rclpy.create_node('integration_talker')
    node.create_publisher(String, '/integration_chatter', 10)
    node.create_subscription(String, '/integration_input', lambda msg: None, 5)
    with _SpinThread(node):
        time.sleep(0.3)  # allow graph discovery
        yield node
    node.destroy_node()


def test_describe_finds_node(talker_node):
    from nodl.describe import describe

    node_msg = describe('/integration_talker', discovery_timeout_sec=1.0)
    assert node_msg.name == '/integration_talker'


def test_describe_publishers(talker_node):
    from nodl.describe import describe

    node_msg = describe('/integration_talker', discovery_timeout_sec=1.0)
    topic_names = [t.name for t in node_msg.publishers]
    assert '/integration_chatter' in topic_names


def test_describe_subscriptions(talker_node):
    from nodl.describe import describe

    node_msg = describe('/integration_talker', discovery_timeout_sec=1.0)
    topic_names = [t.name for t in node_msg.subscriptions]
    assert '/integration_input' in topic_names


def test_describe_to_nodl_valid(talker_node):
    """Full pipeline: describe -> to_nodl -> validate."""
    from nodl.conversion import to_nodl
    from nodl.describe import describe
    from nodl.models import NodlDocument
    from nodl.schema import validate

    node_msg = describe('/integration_talker', discovery_timeout_sec=1.0)
    doc = to_nodl(node_msg)
    assert isinstance(doc, NodlDocument)
    validate(doc.to_dict())  # Must not raise


def test_describe_node_not_found(ros_context):
    from nodl.describe import describe

    with pytest.raises(RuntimeError, match='not found'):
        describe('/nonexistent_node_xyz', discovery_timeout_sec=0.5)
