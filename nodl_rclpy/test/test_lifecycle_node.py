"""Integration tests for NodlLifecycleNode."""
import pytest
import rclpy

from std_msgs.msg import String

from nodl_rclpy import NodlLifecycleNode


@pytest.fixture(autouse=True)
def rclpy_context():
    rclpy.init()
    yield
    rclpy.shutdown()


_NODL_FULL = {
    'node': {'name': 'lc_test_node'},
    'parameters': {
        'rate': {'type': 'double', 'default_value': 5.0},
    },
    'publishers': [
        {'topic': '/lc_out', 'type': 'std_msgs/msg/String'},
    ],
    'subscriptions': [
        {'topic': '/lc_in', 'type': 'std_msgs/msg/String'},
    ],
}


class ConcreteLifecycleNode(NodlLifecycleNode):
    def __init__(self):
        super().__init__(_NODL_FULL)

    def on_lc_in(self, msg: String):
        pass


def test_lifecycle_node_name():
    node = ConcreteLifecycleNode()
    assert node.get_name() == 'lc_test_node'
    node.destroy_node()


def test_lifecycle_node_has_publisher():
    node = ConcreteLifecycleNode()
    assert hasattr(node, 'pub_lc_out_')
    assert node.pub_lc_out_ is not None
    node.destroy_node()


def test_lifecycle_node_has_subscription():
    node = ConcreteLifecycleNode()
    assert hasattr(node, 'sub_lc_in_')
    assert node.sub_lc_in_ is not None
    node.destroy_node()


def test_lifecycle_node_params():
    node = ConcreteLifecycleNode()
    assert hasattr(node, 'params_')
    assert node.params_.rate == pytest.approx(5.0)
    node.destroy_node()


def test_lifecycle_node_is_lifecycle():
    from rclpy.lifecycle import LifecycleNode
    node = ConcreteLifecycleNode()
    assert isinstance(node, LifecycleNode)
    node.destroy_node()
