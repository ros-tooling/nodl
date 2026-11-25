# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Aliases preserve graph names and type prefixes in generated Python."""

import ast
from pathlib import Path

import pytest

from nodl_generator_py.generator import _render_python, generate_python
from nodl_schema import parse_nodl
from nodl_schema.models import NodlDocument


@pytest.mark.parametrize(
    'kind,prefix',
    [
        ('publishers', 'pub_'),
        ('subscriptions', 'sub_'),
        ('service_servers', 'srv_'),
        ('service_clients', 'cli_'),
        ('action_servers', 'action_srv_'),
        ('action_clients', 'action_cli_'),
    ],
)
def test_alias_references(kind, prefix):
    endpoint = {'name': '/long/endpoint', 'type': 'example_interfaces/Fibonacci', 'alias': 'class'}
    if kind in ('publishers', 'subscriptions'):
        endpoint['qos'] = {'history': 'SYSTEM_DEFAULT', 'reliability': 'SYSTEM_DEFAULT'}
    text = _render_python(NodlDocument.parse_obj({'nodl_version': 2, kind: [endpoint]}), 'test_base')
    ast.parse(text)
    assert f'self.{prefix}class =' in text
    assert "'/long/endpoint'" in text
    assert 'long_endpoint' not in text
    if kind in ('subscriptions', 'service_servers'):
        assert 'self.on_class,' in text
        assert 'def on_class(' in text
    if kind == 'action_servers':
        for callback in ('execute_class', 'on_class_goal', 'on_class_cancel'):
            assert f'self.{callback},' in text
            assert f'def {callback}(' in text


@pytest.mark.parametrize(
    'endpoints,symbol',
    [
        (
            {
                'service_clients': [
                    {'name': '/real', 'alias': 'short', 'type': 'std_srvs/Trigger'},
                    {'name': '/short', 'type': 'std_srvs/Trigger'},
                ]
            },
            'cli_short',
        ),
        (
            {
                'service_servers': [{'name': '/real', 'alias': 'short_goal', 'type': 'std_srvs/Trigger'}],
                'action_servers': [{'name': '/action', 'alias': 'short', 'type': 'example_interfaces/Fibonacci'}],
            },
            'on_short_goal',
        ),
    ],
)
def test_alias_collision(endpoints, symbol):
    with pytest.raises(ValueError, match='collision.*' + symbol):
        _render_python(NodlDocument.parse_obj({'nodl_version': 2, **endpoints}), 'test_base')


def test_documented_alias():
    guide = (Path(__file__).parents[1] / 'doc/overview.md').read_text()
    example = guide.split('## Endpoint aliases')[1].split('```yaml\n')[1].split('```')[0]
    text = _render_python(parse_nodl(example), 'test_base')
    ast.parse(text)
    assert 'self.sub_good_name =' in text
    assert 'self.on_good_name,' in text
    assert "'/whatever/my/topic/is'" in text


@pytest.mark.parametrize('collision', [False, True])
def test_aliases_from_includes(tmp_path, collision):
    included = tmp_path / 'included.nodl.yaml'
    included.write_text("""nodl_version: 2
service_clients:
  - name: /long/name
    type: std_srvs/Trigger
    alias: short
""")
    source = tmp_path / 'root.nodl.yaml'
    text = 'nodl_version: 2\ninclude:\n  - ref: local://included.nodl.yaml\n'
    if collision:
        text += 'service_clients:\n  - name: /short\n    type: std_srvs/Trigger\n'
    source.write_text(text)
    if collision:
        with pytest.raises(ValueError, match='collision.*cli_short'):
            generate_python(source, 'test_base')
    else:
        text = generate_python(source, 'test_base').module
        assert 'self.cli_short =' in text
        assert "'/long/name'" in text
