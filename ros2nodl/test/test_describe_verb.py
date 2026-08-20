# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0

import argparse
import json
import os
import threading

import pytest
import yaml

pytest.importorskip('ros2cli')
rclpy = pytest.importorskip('rclpy')

from nodl_schema.validation import validate  # noqa: E402
from ros2nodl.describe._source import observe_binary  # noqa: E402
from ros2nodl.verb.describe import DescribeVerb, _infer_format  # noqa: E402

_TARGET_NODE = '/ros2nodl_test_target'


def _args(**overrides):
    values = {
        'node_name': _TARGET_NODE,
        'from_file': None,
        'timeout': 5.0,
        'no_params': False,
        'include_ros_infra': False,
        'fail_on_warnings': False,
        'output': None,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


@pytest.mark.parametrize(
    'path,format',
    [('out.yaml', 'yaml'), ('out.yml', 'yaml'), ('out.json', 'json'), ('OUT.YAML', 'yaml')],
)
def test_infer_format(path, format):
    assert _infer_format(path) == format


def test_invalid_output_extension_fails(capsys):
    assert DescribeVerb().main(args=_args(output='out.txt')) == 1
    assert 'unrecognised extension' in capsys.readouterr().err


def test_missing_capture_fails_cleanly(capsys):
    assert DescribeVerb().main(args=_args(from_file='/no/such/capture.yaml')) == 1
    assert 'file not found' in capsys.readouterr().err


@pytest.fixture()
def captured_node(tmp_path):
    from rosgraph_msgs.msg import Node, Topic
    from rosidl_runtime_py import message_to_yaml

    message = Node()
    message.name = _TARGET_NODE
    endpoint = Topic()
    endpoint.name = '/chatter'
    endpoint.type.name = 'std_msgs/msg/String'
    endpoint.qos.history = 1
    endpoint.qos.reliability = 1
    endpoint.qos.durability = 2
    endpoint.qos.depth = 10
    # In Lyrical+ msg arrays are type hinted as list, but older distros incorrectly hint it immutable
    message.publishers.append(endpoint)  # pyright: ignore[reportAttributeAccessIssue]
    path = tmp_path / 'capture.yaml'
    path.write_text(message_to_yaml(message))
    return path


def test_from_yaml_emits_valid_nodl(captured_node, capsys):
    assert DescribeVerb().main(args=_args(from_file=str(captured_node))) == 0
    data = yaml.safe_load(capsys.readouterr().out)
    validate(data)
    assert data['nodl_version'] == 2
    assert data['publishers'][0]['name'] == '/chatter'
    assert 'name' not in data


def test_from_yaml_writes_json(captured_node, tmp_path):
    output = tmp_path / 'description.json'
    assert DescribeVerb().main(args=_args(from_file=str(captured_node), output=str(output))) == 0
    assert json.loads(output.read_text())['nodl_version'] == 2


@pytest.fixture(scope='module')
def ros_context():
    os.environ.setdefault('ROS_DOMAIN_ID', '42')
    os.environ.setdefault('ROS_AUTOMATIC_DISCOVERY_RANGE', 'LOCALHOST')
    rclpy.init()
    yield
    rclpy.shutdown()


@pytest.fixture()
def target_node(ros_context):
    from rclpy.executors import SingleThreadedExecutor
    from std_msgs.msg import String

    node = rclpy.create_node(_TARGET_NODE.lstrip('/'))
    node.create_publisher(String, '/test_topic', 10)
    node.create_subscription(String, '/test_topic', lambda _: None, 10)
    executor = SingleThreadedExecutor()
    executor.add_node(node)
    thread = threading.Thread(target=executor.spin, daemon=True)
    thread.start()
    yield
    executor.shutdown()
    thread.join(timeout=3.0)
    node.destroy_node()


@pytest.mark.skipif(observe_binary() is None, reason='observe binary is not installed')
def test_live_describe_emits_valid_nodl(target_node, capsys):
    assert DescribeVerb().main(args=_args()) == 0
    data = yaml.safe_load(capsys.readouterr().out)
    validate(data)
    assert data['nodl_version'] == 2
