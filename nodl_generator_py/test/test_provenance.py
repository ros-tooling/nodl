# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Include-resolution and Python provider tests."""

from pathlib import Path

import pytest

from nodl_generator_py.generator import CodegenError, generate_python_from_file


def _write(path: Path, content: str) -> Path:
    path.write_text(content, encoding='utf-8')
    return path


def _provider(path: Path, class_name: str = 'LifecycleNode', *, entities: bool = True) -> Path:
    entity_yaml = (
        """publishers:
  - name: /rosout
    type: rcl_interfaces/msg/Log
    qos: {history: KEEP_LAST, depth: 1, reliability: RELIABLE}
service_servers:
  - name: ~/change_state
    type: lifecycle_msgs/srv/ChangeState
parameters:
  use_sim_time: {type: bool, default_value: false}
"""
        if entities
        else ''
    )
    return _write(
        path,
        f"""nodl_version: 2
codegen:
  python:
    role: BASE_CLASS
    module: rclpy.lifecycle
    class: {class_name}
    publisher_method: create_lifecycle_publisher
{entity_yaml}
""",
    )


def test_lifecycle_base_and_provider_entities_are_filtered(tmp_path):
    _write(
        tmp_path / 'node.nodl.yaml',
        """nodl_version: 2
publishers:
  - name: /rosout
    type: rcl_interfaces/msg/Log
    qos: {history: KEEP_LAST, depth: 1, reliability: RELIABLE}
parameters:
  use_sim_time: {type: bool, default_value: false}
""",
    )
    _write(
        tmp_path / 'base.nodl.yaml',
        """nodl_version: 2
codegen:
  python:
    role: BASE_CLASS
    module: rclpy.lifecycle
    class: LifecycleNode
    publisher_method: create_lifecycle_publisher
include:
  - ref: local://node.nodl.yaml
service_servers:
  - name: ~/change_state
    type: lifecycle_msgs/srv/ChangeState
""",
    )
    root = _write(
        tmp_path / 'root.nodl.yaml',
        """nodl_version: 2
include:
  - ref: local://base.nodl.yaml
publishers:
  - name: status
    type: std_msgs/msg/String
    qos: {history: KEEP_LAST, depth: 10, reliability: RELIABLE}
""",
    )

    result = generate_python_from_file(root, 'lifecycle_node_base')

    assert 'from rclpy.lifecycle import LifecycleNode' in result.module
    assert 'class LifecycleNodeBase(LifecycleNode):' in result.module
    assert 'self.pub_status = self.create_lifecycle_publisher(' in result.module
    assert '/rosout' not in result.module
    assert 'change_state' not in result.module
    assert result.parameters_yaml is None
    assert result.sources == [
        root.resolve(),
        (tmp_path / 'base.nodl.yaml').resolve(),
        (tmp_path / 'node.nodl.yaml').resolve(),
    ]


def test_two_visible_base_providers_fail_with_both_classes(tmp_path):
    _provider(tmp_path / 'a.nodl.yaml', 'LifecycleNode')
    _provider(tmp_path / 'b.nodl.yaml', 'OtherNode', entities=False)
    root = _write(
        tmp_path / 'root.nodl.yaml',
        """nodl_version: 2
include:
  - ref: local://a.nodl.yaml
  - ref: local://b.nodl.yaml
""",
    )

    with pytest.raises(CodegenError, match='LifecycleNode, OtherNode'):
        generate_python_from_file(root, 'conflict_base')
