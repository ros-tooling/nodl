# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Exercise actual ROS parsing, rather than a Python approximation of its semantics."""

import math

import pytest
import yaml

from ros2nodl.configuration import ParameterValue, resolve_configuration


def test_native_parser_typing_and_node_qualified_parameters():
    values = resolve_configuration(
        node_fqn='/node',
        parameters=[
            'mode:=1_000',
            'enabled:=true',
            'rate:=2.5',
            'label:="true"',
            'items:=[1, 2]',
            'node:limit:=4',
            'other:limit:=99',
            'nan:=nan',
            'precise:=1.2345678901234567',
        ],
    )
    assert values['mode'] == ParameterValue('string', '1_000')
    assert values['enabled'] == ParameterValue('bool', True)
    assert values['rate'] == ParameterValue('double', 2.5)
    assert values['label'] == ParameterValue('string', 'true')
    assert values['items'] == ParameterValue('int_array', [1, 2])
    assert values['limit'] == ParameterValue('int', 4)
    assert math.isnan(values['nan'].value)
    assert values['precise'] == ParameterValue('double', 1.2345678901234567)


def test_native_file_selectors_namespaces_and_precedence(tmp_path):
    first = tmp_path / 'first.yaml'
    first.write_text("""/**:
  ros__parameters:
    limit: 1
    nested:
      enabled: true
/robot:
  node:
    ros__parameters:
      limit: 2
/robot/*:
  ros__parameters:
    mode: wildcard
/elsewhere:
  ros__parameters:
    ignored: 99
""")
    second = tmp_path / 'second.yaml'
    second.write_text('/robot/node:\n  ros__parameters:\n    limit: 3\n')
    values = resolve_configuration(node_fqn='/robot/node', params_files=[first, second])
    assert values == {
        'limit': ParameterValue('int', 3),
        'nested.enabled': ParameterValue('bool', True),
        'mode': ParameterValue('string', 'wildcard'),
    }
    assert (
        resolve_configuration(
            node_fqn='/robot/node', params_files=[first, second], parameters=['limit:=4', 'limit:=5']
        )['limit'].value
        == 3
    )


@pytest.mark.parametrize(
    'value', ['a\nb', 'a\rb', 'a\tb', 'a\u0085b', 'a\u2028b', 'a\u2029b', 'quote" and \\ path', '🤖']
)
def test_native_parser_preserves_string_values(value):
    values = resolve_configuration(
        node_fqn='/node',
        parameters=[
            'text:=' + yaml.safe_dump(value, default_style='"', allow_unicode=False).strip(),
            'texts:=' + yaml.safe_dump([value, 'second'], default_flow_style=True, allow_unicode=False).strip(),
        ],
    )
    assert values['text'] == ParameterValue('string', value)
    assert values['texts'] == ParameterValue('string_array', [value, 'second'])


@pytest.mark.parametrize('selector', ['/**', '/robot/node'])
def test_resolution_matches_actual_node_startup(tmp_path, selector):
    from rclpy.context import Context
    from rclpy.node import Node

    file = tmp_path / 'deployment.yaml'
    file.write_text(f'{selector}:\n  ros__parameters:\n    limit: 3\n')
    expected = resolve_configuration(node_fqn='/robot/node', params_files=[file], parameters=['limit:=5'])
    context = Context()
    context.init(args=[])
    try:
        node = Node(
            'node',
            namespace='/robot',
            context=context,
            enable_rosout=False,
            start_parameter_services=False,
            use_global_arguments=False,
            automatically_declare_parameters_from_overrides=True,
            cli_args=['--ros-args', '--params-file', str(file), '-p', 'limit:=5'],
        )
        try:
            assert expected['limit'].value == node.get_parameter('limit').value
        finally:
            node.destroy_node()
    finally:
        context.shutdown()


@pytest.mark.parametrize('item', ['bad', 'x:=[1, true]', 'x:={a: 1}'])
def test_native_parser_rejects_invalid_inputs(item):
    with pytest.raises(ValueError):
        resolve_configuration(node_fqn='/node', parameters=[item])


def test_missing_and_invalid_files_fail(tmp_path):
    with pytest.raises(ValueError):
        resolve_configuration(node_fqn='/node', params_files=[tmp_path / 'missing.yaml'])
    invalid = tmp_path / 'invalid.yaml'
    invalid.write_text('/node:\n  ros__parameters: [\n')
    with pytest.raises(ValueError):
        resolve_configuration(node_fqn='/node', params_files=[invalid])


def test_no_inputs_do_not_require_the_native_helper(monkeypatch):
    import subprocess

    monkeypatch.setattr(subprocess, 'run', lambda *a, **kw: pytest.fail('unexpected native parser'))
    assert resolve_configuration(node_fqn='/node') == {}
