"""Unit tests for nodl_generator_rust — no rclrs or live ROS required."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from nodl_generator_rust.generator import (
    _build_context,
    _default_expr,
    _qos_call,
    _ros_type_to_crate,
    _ros_type_to_rust,
    _to_pascal,
    _to_snake,
)


# ---------------------------------------------------------------------------
# Name helpers
# ---------------------------------------------------------------------------

def test_to_snake_strips_leading_slash():
    assert _to_snake('/scan') == 'scan'


def test_to_snake_replaces_slashes():
    assert _to_snake('/my/long/topic') == 'my_long_topic'


def test_to_pascal():
    assert _to_pascal('my_node') == 'MyNode'


# ---------------------------------------------------------------------------
# ROS type helpers
# ---------------------------------------------------------------------------

def test_ros_type_to_rust():
    assert _ros_type_to_rust('sensor_msgs/msg/LaserScan') == 'sensor_msgs::msg::LaserScan'


def test_ros_type_to_crate():
    assert _ros_type_to_crate('sensor_msgs/msg/LaserScan') == 'sensor_msgs'


# ---------------------------------------------------------------------------
# QoS
# ---------------------------------------------------------------------------

def test_qos_call_none_defaults_to_reliable_10():
    result = _qos_call(None)
    assert 'reliable' in result
    assert '10' in result


def test_qos_call_best_effort():
    result = _qos_call({'history': 5, 'reliability': 'BEST_EFFORT'})
    assert 'BEST_EFFORT' in result
    assert '5' in result


def test_qos_call_keep_all():
    result = _qos_call({'history': 'ALL', 'reliability': 'RELIABLE'})
    assert 'ALL' in result


def test_qos_call_transient_local():
    result = _qos_call({'history': 10, 'reliability': 'RELIABLE', 'durability': 'TRANSIENT_LOCAL'})
    assert 'TRANSIENT_LOCAL' in result


# ---------------------------------------------------------------------------
# Default value expressions
# ---------------------------------------------------------------------------

def test_default_expr_double():
    assert _default_expr('double', 10.0) == '10.0_f64'


def test_default_expr_int():
    assert _default_expr('int', 42) == '42_i64'


def test_default_expr_bool_true():
    assert _default_expr('bool', True) == 'true'


def test_default_expr_string():
    assert _default_expr('string', 'hello') == '"hello".to_string()'


def test_default_expr_none_returns_none():
    assert _default_expr('double', None) is None


def test_default_expr_string_array():
    result = _default_expr('string_array', ['a', 'b'])
    assert 'vec!' in result


# ---------------------------------------------------------------------------
# Context builder
# ---------------------------------------------------------------------------

_FULL_NODL = {
    'node': {'name': 'my_sensor_node'},
    'publishers': [
        {'topic': '/scan', 'type': 'sensor_msgs/msg/LaserScan'},
        {'topic': '/cloud', 'type': 'sensor_msgs/msg/PointCloud2',
         'qos': {'history': 5, 'reliability': 'BEST_EFFORT'}},
    ],
    'subscriptions': [
        {'topic': '/cmd_vel', 'type': 'geometry_msgs/msg/Twist'},
    ],
    'service_servers': [
        {'name': '/reset', 'type': 'std_srvs/srv/Trigger'},
    ],
    'service_clients': [
        {'name': '/set_mode', 'type': 'std_srvs/srv/SetBool'},
    ],
    'parameters': {
        'rate': {'type': 'double', 'default_value': 10.0},
        'label': {'type': 'string'},
        'enabled': {'type': 'bool', 'default_value': True, 'read_only': True},
    },
}


def test_context_struct_name():
    ctx = _build_context(_FULL_NODL, 'my_sensor_node')
    assert ctx['struct_name'] == 'MySensorNode'


def test_context_publishers_count():
    ctx = _build_context(_FULL_NODL, 'my_sensor_node')
    assert len(ctx['publishers']) == 2


def test_context_publisher_ident():
    ctx = _build_context(_FULL_NODL, 'my_sensor_node')
    assert ctx['publishers'][0]['ident'] == 'scan'


def test_context_subscriptions_builder_method():
    ctx = _build_context(_FULL_NODL, 'my_sensor_node')
    assert ctx['subscriptions'][0]['builder_method'] == 'on_cmd_vel'


def test_context_service_servers_builder_method():
    ctx = _build_context(_FULL_NODL, 'my_sensor_node')
    assert ctx['service_servers'][0]['builder_method'] == 'on_reset'


def test_context_parameters_has_default():
    ctx = _build_context(_FULL_NODL, 'my_sensor_node')
    by_name = {p['name']: p for p in ctx['parameters']}
    assert by_name['rate']['has_default'] is True
    assert by_name['label']['has_default'] is False


def test_context_parameters_read_only():
    ctx = _build_context(_FULL_NODL, 'my_sensor_node')
    by_name = {p['name']: p for p in ctx['parameters']}
    assert by_name['enabled']['read_only'] is True
    assert by_name['rate']['read_only'] is False


def test_context_crates_collected():
    ctx = _build_context(_FULL_NODL, 'my_sensor_node')
    assert 'sensor_msgs' in ctx['crates']
    assert 'geometry_msgs' in ctx['crates']
    assert 'std_srvs' in ctx['crates']


def test_context_empty_nodl():
    ctx = _build_context({}, 'empty_node')
    assert ctx['publishers'] == []
    assert ctx['parameters'] == []
    assert ctx['crates'] == []


# ---------------------------------------------------------------------------
# End-to-end render smoke test
# ---------------------------------------------------------------------------

def test_render_produces_valid_rust_fragment(tmp_path):
    import jinja2
    templates_dir = Path(__file__).parent.parent / 'nodl_generator_rust' / 'templates'
    assert templates_dir.exists(), f"Templates dir not found: {templates_dir}"
    loader = jinja2.FileSystemLoader(str(templates_dir))
    env = jinja2.Environment(loader=loader, trim_blocks=True, lstrip_blocks=True)
    ctx = _build_context(_FULL_NODL, 'my_sensor_node')
    output = env.get_template('node_nodl.rs.jinja2').render(**ctx)

    # Structural checks on the generated Rust source
    assert 'pub struct MySensorNodeNodl' in output
    assert 'pub struct MySensorNodeBuilder' in output
    assert 'pub struct MySensorNodeParams' in output
    assert 'pub struct MySensorNodePublishers' in output
    assert 'pub struct MySensorNodeClients' in output
    assert 'TOPIC_SCAN' in output
    assert 'TOPIC_CMD_VEL' in output
    assert 'SERVICE_RESET' in output
    assert 'on_cmd_vel' in output
    assert 'on_reset' in output
    assert 'declare_params' in output
    assert '10.0_f64' in output       # rate default
    assert 'Option<String>' in output  # label has no default
