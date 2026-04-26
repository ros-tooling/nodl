"""Unit tests for the nodl_generate_cpp Python generator."""

from __future__ import annotations

import importlib.machinery
import importlib.util
import sys
from pathlib import Path

import pytest

# Load the generator script as a module (it has no .py extension).
_SCRIPT = Path(__file__).parents[1] / 'scripts' / 'nodl_generate_cpp'
_loader = importlib.machinery.SourceFileLoader('nodl_generate_cpp', str(_SCRIPT))
_spec = importlib.util.spec_from_loader('nodl_generate_cpp', _loader)
_mod = importlib.util.module_from_spec(_spec)
_loader.exec_module(_mod)

camel_to_snake = _mod._camel_to_snake
snake_to_pascal = _mod._snake_to_pascal
topic_to_identifier = _mod._topic_to_identifier
ros_type_to_cpp = _mod._ros_type_to_cpp
ros_type_to_include = _mod._ros_type_to_include
qos_to_cpp = _mod._qos_to_cpp
build_context = _mod._build_context


# ---------------------------------------------------------------------------
# Name conversions
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('name,expected', [
    ('Image', 'image'),
    ('LaserScan', 'laser_scan'),
    ('PointCloud2', 'point_cloud2'),
    ('NavSatFix', 'nav_sat_fix'),
    ('String', 'string'),
])
def test_camel_to_snake(name, expected):
    assert camel_to_snake(name) == expected


@pytest.mark.parametrize('name,expected', [
    ('my_node', 'MyNode'),
    ('test', 'Test'),
    ('foo_bar_baz', 'FooBarBaz'),
])
def test_snake_to_pascal(name, expected):
    assert snake_to_pascal(name) == expected


@pytest.mark.parametrize('topic,expected', [
    ('/scan', 'scan'),
    ('/my/long/topic', 'my_long_topic'),
    ('relative', 'relative'),
    ('/a/b', 'a_b'),
])
def test_topic_to_identifier(topic, expected):
    assert topic_to_identifier(topic) == expected


# ---------------------------------------------------------------------------
# Type conversions
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('ros_type,expected_cpp', [
    ('sensor_msgs/msg/Image', 'sensor_msgs::msg::Image'),
    ('std_msgs/msg/String', 'std_msgs::msg::String'),
    ('std_srvs/srv/SetBool', 'std_srvs::srv::SetBool'),
])
def test_ros_type_to_cpp(ros_type, expected_cpp):
    assert ros_type_to_cpp(ros_type) == expected_cpp


@pytest.mark.parametrize('ros_type,expected_include', [
    ('sensor_msgs/msg/Image', 'sensor_msgs/msg/image.hpp'),
    ('sensor_msgs/msg/LaserScan', 'sensor_msgs/msg/laser_scan.hpp'),
    ('sensor_msgs/msg/PointCloud2', 'sensor_msgs/msg/point_cloud2.hpp'),
    ('std_msgs/msg/String', 'std_msgs/msg/string.hpp'),
])
def test_ros_type_to_include(ros_type, expected_include):
    assert ros_type_to_include(ros_type) == expected_include


# ---------------------------------------------------------------------------
# qos_to_cpp
# ---------------------------------------------------------------------------

def test_qos_to_cpp_default():
    assert qos_to_cpp(None) == 'rclcpp::QoS(10)'


def test_qos_to_cpp_reliable():
    result = qos_to_cpp({'history': 10, 'reliability': 'RELIABLE'})
    assert result == 'rclcpp::QoS(10).reliable()'


def test_qos_to_cpp_best_effort():
    result = qos_to_cpp({'history': 5, 'reliability': 'BEST_EFFORT'})
    assert result == 'rclcpp::QoS(5).best_effort()'


def test_qos_to_cpp_keep_all():
    result = qos_to_cpp({'history': 'ALL', 'reliability': 'RELIABLE'})
    assert result == 'rclcpp::QoS(rclcpp::KeepAll()).reliable()'


def test_qos_to_cpp_transient_local():
    result = qos_to_cpp({
        'history': 10,
        'reliability': 'RELIABLE',
        'durability': 'TRANSIENT_LOCAL',
    })
    assert result == 'rclcpp::QoS(10).reliable().transient_local()'


# ---------------------------------------------------------------------------
# build_context
# ---------------------------------------------------------------------------

_MINIMAL_NODL = {
    'node': {'name': 'my_node'},
}

_FULL_NODL = {
    'node': {'name': 'test_node'},
    'parameters': {
        'rate': {'type': 'double', 'default_value': 5.0},
        'name': {'type': 'string', 'read_only': True},
    },
    'publishers': [
        {
            'topic': '/scan',
            'type': 'sensor_msgs/msg/LaserScan',
            'qos': {'history': 10, 'reliability': 'RELIABLE'},
        }
    ],
    'subscriptions': [
        {
            'topic': '/cmd',
            'type': 'std_msgs/msg/String',
        }
    ],
}


def test_build_context_class_name():
    ctx = build_context(_MINIMAL_NODL, 'my_node', lifecycle=False)
    assert ctx['class_name'] == 'MyNodeBase'


def test_build_context_node_name():
    ctx = build_context(_FULL_NODL, 'test_node', lifecycle=False)
    assert ctx['node_name'] == 'test_node'


def test_build_context_base_class_regular():
    ctx = build_context(_MINIMAL_NODL, 'x', lifecycle=False)
    assert ctx['base_class'] == 'rclcpp::Node'


def test_build_context_base_class_lifecycle():
    ctx = build_context(_MINIMAL_NODL, 'x', lifecycle=True)
    assert ctx['base_class'] == 'rclcpp_lifecycle::LifecycleNode'


def test_build_context_includes_rclcpp():
    ctx = build_context(_MINIMAL_NODL, 'x', lifecycle=False)
    assert 'rclcpp/rclcpp.hpp' in ctx['includes']


def test_build_context_includes_lifecycle():
    ctx = build_context(_MINIMAL_NODL, 'x', lifecycle=True)
    assert 'rclcpp_lifecycle/lifecycle_node.hpp' in ctx['includes']


def test_build_context_has_params_true():
    ctx = build_context(_FULL_NODL, 'test_node', lifecycle=False)
    assert ctx['has_params'] is True


def test_build_context_has_params_false_when_no_parameters():
    ctx = build_context(_MINIMAL_NODL, 'my_node', lifecycle=False)
    assert ctx['has_params'] is False


def test_build_context_params_namespace():
    ctx = build_context(_FULL_NODL, 'test_node', lifecycle=False)
    assert ctx['params_namespace'] == 'test_node'


def test_build_context_publishers():
    ctx = build_context(_FULL_NODL, 'test_node', lifecycle=False)
    assert len(ctx['publishers']) == 1
    pub = ctx['publishers'][0]
    assert pub['topic'] == '/scan'
    assert pub['cpp_type'] == 'sensor_msgs::msg::LaserScan'
    assert pub['member_name'] == 'pub_scan_'
    assert 'sensor_msgs/msg/laser_scan.hpp' in ctx['includes']


def test_build_context_subscriptions():
    ctx = build_context(_FULL_NODL, 'test_node', lifecycle=False)
    assert len(ctx['subscriptions']) == 1
    sub = ctx['subscriptions'][0]
    assert sub['topic'] == '/cmd'
    assert sub['cpp_type'] == 'std_msgs::msg::String'
    assert sub['member_name'] == 'sub_cmd_'
    assert sub['callback_name'] == 'on_cmd'


def test_build_context_no_duplicate_includes():
    nodl = {
        'publishers': [
            {'topic': '/a', 'type': 'std_msgs/msg/String'},
            {'topic': '/b', 'type': 'std_msgs/msg/String'},
        ]
    }
    ctx = build_context(nodl, 'x', lifecycle=False)
    assert ctx['includes'].count('std_msgs/msg/string.hpp') == 1


def test_build_context_empty_nodl():
    ctx = build_context({}, 'my_target', lifecycle=False)
    assert ctx['class_name'] == 'MyTargetBase'
    assert ctx['has_params'] is False
    assert ctx['publishers'] == []
    assert ctx['subscriptions'] == []


# ---------------------------------------------------------------------------
# _write_params_yaml
# ---------------------------------------------------------------------------

def test_write_params_yaml_structure(tmp_path):
    import yaml

    params = {
        'rate': {'type': 'double', 'default_value': 5.0},
        'label': {'type': 'string', 'read_only': True},
    }
    out = tmp_path / 'test_params.yaml'
    _mod._write_params_yaml(out, 'my_node', params)
    data = yaml.safe_load(out.read_text())
    assert 'my_node' in data
    assert data['my_node']['rate']['type'] == 'double'
    assert data['my_node']['label']['read_only'] is True


# ---------------------------------------------------------------------------
# Template rendering (requires jinja2)
# ---------------------------------------------------------------------------

jinja2 = pytest.importorskip('jinja2')

_TEMPLATES_DIR = Path(__file__).parents[1] / 'templates'


def _render(template_name: str, context: dict) -> str:
    loader = jinja2.FileSystemLoader(str(_TEMPLATES_DIR))
    env = jinja2.Environment(loader=loader, trim_blocks=True, lstrip_blocks=True)
    return env.get_template(template_name).render(**context)


def test_render_hpp_contains_class():
    ctx = build_context(_FULL_NODL, 'test_node', lifecycle=False)
    hpp = _render('node.hpp.jinja2', ctx)
    assert 'class TestNodeBase' in hpp
    assert 'public rclcpp::Node' in hpp
    assert 'pub_scan_' in hpp
    assert 'on_cmd' in hpp
    assert 'virtual void on_cmd' in hpp


def test_render_hpp_params_via_genparamlib():
    ctx = build_context(_FULL_NODL, 'test_node', lifecycle=False)
    hpp = _render('node.hpp.jinja2', ctx)
    assert 'test_node_params.hpp' in hpp
    assert 'test_node::ParamListener param_listener_' in hpp
    assert 'test_node::Params params_' in hpp


def test_render_cpp_uses_param_listener():
    ctx = build_context(_FULL_NODL, 'test_node', lifecycle=False)
    cpp = _render('node.cpp.jinja2', ctx)
    assert 'TestNodeBase::TestNodeBase' in cpp
    # Initializer list — not assignment in body
    assert ', param_listener_(get_node_parameters_interface())' in cpp
    assert ', params_(param_listener_.get_params())' in cpp
    assert 'create_publisher' in cpp
    assert 'create_subscription' in cpp
    assert 'on_cmd' in cpp


def test_render_cpp_no_declare_parameter():
    """Parameters are handled by generate_parameter_library, not inline calls."""
    ctx = build_context(_FULL_NODL, 'test_node', lifecycle=False)
    cpp = _render('node.cpp.jinja2', ctx)
    assert 'declare_parameter' not in cpp


def test_render_hpp_lifecycle():
    nodl = {'node': {'name': 'my_node'}}
    ctx = build_context(nodl, 'my_node', lifecycle=True)
    hpp = _render('node.hpp.jinja2', ctx)
    assert 'rclcpp_lifecycle::LifecycleNode' in hpp


def test_render_hpp_no_params_section_when_empty():
    ctx = build_context({}, 'empty_node', lifecycle=False)
    hpp = _render('node.hpp.jinja2', ctx)
    assert 'params_' not in hpp
    assert 'ParamListener' not in hpp
    assert 'Publishers' not in hpp
    assert 'Subscriptions' not in hpp


def test_render_cpp_no_param_listener_when_no_params():
    ctx = build_context(_MINIMAL_NODL, 'my_node', lifecycle=False)
    cpp = _render('node.cpp.jinja2', ctx)
    assert 'ParamListener' not in cpp
    assert 'get_params' not in cpp
