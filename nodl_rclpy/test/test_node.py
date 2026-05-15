"""Integration tests for NodlNode."""
import pytest
import rclpy

from std_msgs.msg import String

from nodl_rclpy import NodlNode


@pytest.fixture(autouse=True)
def rclpy_context():
    rclpy.init()
    yield
    rclpy.shutdown()


_NODL_FULL = {
    'node': {'name': 'test_node'},
    'parameters': {
        'publish_rate': {'type': 'double', 'default_value': 10.0},
        'frame_id': {'type': 'string', 'default_value': 'base_link'},
        'enabled': {'type': 'bool', 'default_value': True, 'read_only': True},
    },
    'publishers': [
        {'topic': '/output', 'type': 'std_msgs/msg/String',
         'qos': {'history': 10, 'reliability': 'RELIABLE'}},
    ],
    'subscriptions': [
        {'topic': '/input', 'type': 'std_msgs/msg/String',
         'qos': {'history': 5, 'reliability': 'BEST_EFFORT'}},
    ],
}

_NODL_MINIMAL = {
    'node': {'name': 'minimal_node'},
}


class ConcreteNode(NodlNode):
    def __init__(self, nodl=_NODL_FULL):
        super().__init__(nodl)
        self.input_count = 0

    def on_input(self, msg: String):
        self.input_count += 1


class MinimalNode(NodlNode):
    def __init__(self):
        super().__init__(_NODL_MINIMAL)


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------

def test_node_name_from_nodl():
    node = ConcreteNode()
    assert node.get_name() == 'test_node'
    node.destroy_node()


def test_node_name_override():
    node = NodlNode(_NODL_MINIMAL, node_name='overridden')
    assert node.get_name() == 'overridden'
    node.destroy_node()


def test_no_name_raises():
    with pytest.raises(ValueError):
        NodlNode({'publishers': []})


def test_dict_source():
    node = MinimalNode()
    assert node.get_name() == 'minimal_node'
    node.destroy_node()


# ---------------------------------------------------------------------------
# Publishers
# ---------------------------------------------------------------------------

def test_publisher_exists():
    node = ConcreteNode()
    assert hasattr(node, 'pub_output_')
    assert node.pub_output_ is not None
    node.destroy_node()


def test_publisher_correct_type():
    node = ConcreteNode()
    assert node.pub_output_.msg_type is String
    node.destroy_node()


# ---------------------------------------------------------------------------
# Subscriptions
# ---------------------------------------------------------------------------

def test_subscription_exists():
    node = ConcreteNode()
    assert hasattr(node, 'sub_input_')
    assert node.sub_input_ is not None
    node.destroy_node()


def test_subscription_missing_callback_skipped(caplog):
    import logging

    class NoCallbackNode(NodlNode):
        def __init__(self):
            super().__init__(_NODL_FULL)

    with caplog.at_level(logging.WARNING):
        node = NoCallbackNode()
    assert not hasattr(node, 'sub_input_')
    node.destroy_node()


# ---------------------------------------------------------------------------
# Parameters
# ---------------------------------------------------------------------------

def test_params_attribute_exists():
    node = ConcreteNode()
    assert hasattr(node, 'params_')
    node.destroy_node()


def test_param_listener_attribute_exists():
    node = ConcreteNode()
    assert hasattr(node, 'param_listener_')
    node.destroy_node()


def test_default_param_values():
    node = ConcreteNode()
    assert node.params_.publish_rate == pytest.approx(10.0)
    assert node.params_.frame_id == 'base_link'
    assert node.params_.enabled is True
    node.destroy_node()


def test_params_declared_on_node():
    node = ConcreteNode()
    assert node.has_parameter('publish_rate')
    assert node.has_parameter('frame_id')
    assert node.has_parameter('enabled')
    node.destroy_node()


def test_read_only_param():
    node = ConcreteNode()
    desc = node.describe_parameter('enabled')
    assert desc.read_only is True
    node.destroy_node()


def test_no_params_section_no_listener():
    node = MinimalNode()
    assert not hasattr(node, 'param_listener_')
    assert not hasattr(node, 'params_')
    node.destroy_node()


# ---------------------------------------------------------------------------
# File path source
# ---------------------------------------------------------------------------

def test_file_path_source(tmp_path):
    nodl_file = tmp_path / 'my_node.nodl.yaml'
    nodl_file.write_text(
        'nodl_version: "1"\n'
        'node:\n'
        '  name: file_node\n'
    )
    node = NodlNode(nodl_file)
    assert node.get_name() == 'file_node'
    node.destroy_node()
