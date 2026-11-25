# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Document-tree walk and Python provider tests."""

from pathlib import Path

import pytest

from nodl_generator_common.plan import CodegenError
from nodl_generator_py import generate_python


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


def _no_generate(path: Path, *, include: str | None = None) -> Path:
    include_yaml = f'include:\n  - ref: local://{include}\n' if include is not None else ''
    return _write(
        path,
        f"""nodl_version: 2
codegen:
  python:
    role: NO_GENERATE
{include_yaml}publishers:
  - name: /ignored
    type: sensor_msgs/msg/Image
    qos: {{history: KEEP_LAST, depth: 1, reliability: RELIABLE}}
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

    result = generate_python(root, 'lifecycle_node_base')

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
        generate_python(root, 'conflict_base')


def test_no_generate_filters_entities_without_selecting_base(tmp_path):
    _provider(tmp_path / 'base.nodl.yaml', entities=False)
    ignored = _no_generate(tmp_path / 'ignored.nodl.yaml')
    root = _write(
        tmp_path / 'root.nodl.yaml',
        """nodl_version: 2
include:
  - ref: local://base.nodl.yaml
  - ref: local://ignored.nodl.yaml
publishers:
  - name: status
    type: std_msgs/msg/String
    qos: {history: KEEP_LAST, depth: 10, reliability: RELIABLE}
""",
    )

    result = generate_python(root, 'example_node_base')

    assert 'from rclpy.lifecycle import LifecycleNode' in result.module
    assert 'import std_msgs.msg' in result.module
    assert 'sensor_msgs' not in result.module
    assert '/ignored' not in result.module
    assert ignored.resolve() in result.sources


def test_no_generate_hides_transitive_base_class(tmp_path):
    _provider(tmp_path / 'base.nodl.yaml', entities=False)
    _no_generate(tmp_path / 'ignored.nodl.yaml', include='base.nodl.yaml')
    root = _write(
        tmp_path / 'root.nodl.yaml',
        """nodl_version: 2
include:
  - ref: local://ignored.nodl.yaml
""",
    )

    result = generate_python(root, 'example_node_base')

    assert 'from rclpy.node import Node' in result.module
    assert 'LifecycleNode' not in result.module
    assert '/ignored' not in result.module


def test_root_cpp_node_metadata_is_ignored(tmp_path):
    _provider(tmp_path / 'base.nodl.yaml', entities=False)
    root = _write(
        tmp_path / 'root.nodl.yaml',
        """nodl_version: 2
codegen:
  cpp:
    role: NODE
    namespace: my_pkg::nodes
include:
  - ref: local://base.nodl.yaml
publishers:
  - name: status
    type: std_msgs/msg/String
    qos: {history: KEEP_LAST, depth: 10, reliability: RELIABLE}
""",
    )

    result = generate_python(root, 'example_node_base')

    assert 'from rclpy.lifecycle import LifecycleNode' in result.module
    assert 'my_pkg' not in result.module


@pytest.mark.parametrize('role', ['BASE_CLASS', 'NO_GENERATE'])
def test_root_python_provider_metadata_is_rejected(tmp_path, role):
    root = tmp_path / 'root.nodl.yaml'
    if role == 'BASE_CLASS':
        _provider(root, entities=False)
    else:
        _no_generate(root)

    with pytest.raises(CodegenError, match=f'root document has codegen.python role {role}'):
        generate_python(root, 'example_node_base')


_LIFECYCLE_ROOT = """nodl_version: 2
include:
  - ref: local://base.nodl.yaml
publishers:
  - name: status
    type: std_msgs/msg/String
    qos: {history: KEEP_LAST, depth: 10, reliability: RELIABLE}
subscriptions:
  - name: cmd
    type: std_msgs/msg/String
    qos: {history: KEEP_LAST, depth: 1, reliability: BEST_EFFORT}
  - name: latched
    type: std_msgs/msg/String
    qos: {history: KEEP_LAST, depth: 1, reliability: RELIABLE, durability: TRANSIENT_LOCAL}
service_servers:
  - name: trigger
    type: std_srvs/srv/Trigger
"""


def _lifecycle_base(path: Path, lifecycle: str) -> Path:
    return _write(
        path,
        f"""nodl_version: 2
codegen:
  python:
    role: BASE_CLASS
    module: nodl_runtime_py.lifecycle
    class: LifecycleNode
    publisher_method: create_lifecycle_publisher
{lifecycle}
""",
    )


def test_lifecycle_base_declares_subscriptions_and_service_servers_as_managed(tmp_path):
    _lifecycle_base(tmp_path / 'base.nodl.yaml', '    lifecycle: true')
    root = _write(tmp_path / 'root.nodl.yaml', _LIFECYCLE_ROOT)

    module = generate_python(root, 'lifecycle_node_base').module

    assert 'from nodl_runtime_py.managed import Managed' in module
    for name in ('cmd', 'latched'):
        assert f'self.sub_{name} = Managed(' in module
        assert f'self.sub_{name} = self.create_subscription(' not in module
        assert 'lambda: self.create_subscription(' in module
        assert f'self.on_{name},' in module
    assert module.count('self.destroy_subscription,') == 2
    assert 'durability=rclpy.qos.DurabilityPolicy.TRANSIENT_LOCAL' in module
    assert module.index('self.sub_cmd = ') < module.index('self.sub_latched = ')
    assert 'self.pub_status = self.create_lifecycle_publisher(' in module
    assert 'self.srv_trigger = Managed(' in module
    assert 'lambda: self.create_service(' in module
    assert 'self.on_trigger,' in module
    assert module.count('self.destroy_service,') == 1
    assert 'self.srv_trigger = self.create_service(' not in module
    assert module.index('self.sub_latched = ') < module.index('self.srv_trigger = ')
    compile(module, 'lifecycle_node_base.py', 'exec')


@pytest.mark.parametrize('lifecycle', ['', '    lifecycle: false'])
def test_non_lifecycle_base_creates_endpoints_directly(tmp_path, lifecycle):
    _lifecycle_base(tmp_path / 'base.nodl.yaml', lifecycle)
    root = _write(tmp_path / 'root.nodl.yaml', _LIFECYCLE_ROOT)

    module = generate_python(root, 'lifecycle_node_base').module

    assert 'Managed' not in module
    assert 'destroy_subscription' not in module
    assert 'destroy_service' not in module
    assert 'self.srv_trigger = self.create_service(' in module
    assert 'self.sub_cmd = self.create_subscription(' in module
    assert 'self.sub_latched = self.create_subscription(' in module


def test_lifecycle_base_without_subscriptions_does_not_import_managed(tmp_path):
    _lifecycle_base(tmp_path / 'base.nodl.yaml', '    lifecycle: true')
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

    assert 'Managed' not in generate_python(root, 'lifecycle_node_base').module


def test_lifecycle_base_with_only_service_servers_imports_managed(tmp_path):
    _lifecycle_base(tmp_path / 'base.nodl.yaml', '    lifecycle: true')
    root = _write(
        tmp_path / 'root.nodl.yaml',
        """nodl_version: 2
include:
  - ref: local://base.nodl.yaml
service_servers:
  - name: trigger
    type: std_srvs/srv/Trigger
    qos: {history: KEEP_LAST, depth: 5, reliability: RELIABLE}
""",
    )

    module = generate_python(root, 'lifecycle_node_base').module

    assert 'from nodl_runtime_py.managed import Managed' in module
    assert 'self.srv_trigger = Managed(' in module
    assert 'qos_profile=rclpy.qos.QoSProfile(' in module
    compile(module, 'lifecycle_node_base.py', 'exec')
