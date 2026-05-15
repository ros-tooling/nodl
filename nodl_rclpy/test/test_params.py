"""Tests for NodlParameterListener and NodlParams."""
import pytest
import rclpy

from nodl_rclpy.params import NodlParameterListener, NodlParams
from nodl.models import Parameter


@pytest.fixture(autouse=True)
def rclpy_context():
    rclpy.init()
    yield
    rclpy.shutdown()


def _make_node(name='test_params_node'):
    return rclpy.create_node(name)


_PARAMS_SCHEMA = {
    'rate': Parameter(type='double', default_value=10.0, description='Publish rate'),
    'frame_id': Parameter(type='string', default_value='base_link'),
    'enabled': Parameter(type='bool', default_value=True, read_only=True),
}


def test_listener_declares_parameters():
    node = _make_node()
    NodlParameterListener(node, _PARAMS_SCHEMA)
    assert node.has_parameter('rate')
    assert node.has_parameter('frame_id')
    assert node.has_parameter('enabled')
    node.destroy_node()


def test_get_params_returns_nodl_params():
    node = _make_node()
    listener = NodlParameterListener(node, _PARAMS_SCHEMA)
    params = listener.get_params()
    assert isinstance(params, NodlParams)
    node.destroy_node()


def test_params_default_values():
    node = _make_node()
    listener = NodlParameterListener(node, _PARAMS_SCHEMA)
    params = listener.get_params()
    assert params.rate == pytest.approx(10.0)
    assert params.frame_id == 'base_link'
    assert params.enabled is True
    node.destroy_node()


def test_read_only_parameter():
    from rcl_interfaces.msg import ParameterType
    node = _make_node()
    NodlParameterListener(node, _PARAMS_SCHEMA)
    desc = node.describe_parameter('enabled')
    assert desc.read_only is True
    node.destroy_node()


def test_snapshot_updates_on_set_parameter():
    node = _make_node()
    listener = NodlParameterListener(node, _PARAMS_SCHEMA)
    node.set_parameters([rclpy.parameter.Parameter('rate', value=20.0)])
    params = listener.get_params()
    assert params.rate == pytest.approx(20.0)
    node.destroy_node()


def test_no_default_value_declares_by_type():
    schema = {'count': Parameter(type='int')}
    node = _make_node()
    NodlParameterListener(node, schema)
    assert node.has_parameter('count')
    node.destroy_node()
