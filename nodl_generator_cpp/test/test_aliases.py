# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Endpoint aliases flow through declarations and every generated reference."""

from pathlib import Path

import pytest
import yaml

from nodl_generator_cpp.template import render_templates
from nodl_schema import parse_nodl
from nodl_schema.models import ActionEndpoint, ServiceEndpoint, TopicEndpoint


def render(**endpoints):
    kinds = ('publishers', 'subscriptions', 'service_servers', 'service_clients', 'action_servers', 'action_clients')
    return '\n'.join(
        file.content
        for file in render_templates(
            'test_base',
            'rclcpp::Node',
            'rclcpp/rclcpp.hpp',
            *(endpoints.get(kind, []) for kind in kinds),
            publisher_class='rclcpp::Publisher',
        )
    )


@pytest.mark.parametrize(
    'kind,model,prefix',
    [
        ('publishers', TopicEndpoint, 'pub_'),
        ('subscriptions', TopicEndpoint, 'sub_'),
        ('service_servers', ServiceEndpoint, 'srv_'),
        ('service_clients', ServiceEndpoint, 'cli_'),
        ('action_servers', ActionEndpoint, 'action_srv_'),
        ('action_clients', ActionEndpoint, 'action_cli_'),
    ],
)
def test_alias_references(kind, model, prefix):
    kwargs = {'qos': {'history': 'SYSTEM_DEFAULT', 'reliability': 'SYSTEM_DEFAULT'}} if model is TopicEndpoint else {}
    endpoint = model(name='/long/endpoint', type='example_interfaces/Fibonacci', alias='class', **kwargs)
    text = render(**{kind: [endpoint]})
    assert text.count(prefix + 'class_') == 2
    assert '"/long/endpoint"' in text
    assert 'long_endpoint' not in text
    if kind in ('subscriptions', 'service_servers'):
        assert text.count('on_class') == 2
    if kind == 'action_servers':
        for suffix in ('goal', 'cancel', 'accepted'):
            assert text.count('on_class_' + suffix) == 2


def test_alias_collides_with_default_name():
    with pytest.raises(ValueError, match='collision.*cli_short_'):
        render(
            service_clients=[
                ServiceEndpoint(name='/long/endpoint', type='std_srvs/Trigger', alias='short'),
                ServiceEndpoint(name='/short', type='std_srvs/Trigger'),
            ]
        )


def test_callbacks_can_overload():
    text = render(
        service_servers=[ServiceEndpoint(name='/service', type='std_srvs/Trigger', alias='short_goal')],
        action_servers=[ActionEndpoint(name='/action', type='example_interfaces/Fibonacci', alias='short')],
    )
    assert text.count('on_short_goal') == 4


@pytest.mark.parametrize('alias', ['bad__name', 'trailing_'])
def test_cpp_reserved_alias(alias):
    with pytest.raises(ValueError, match='reserved double underscores'):
        render(service_clients=[ServiceEndpoint(name='/real', type='std_srvs/Trigger', alias=alias)])


def test_documented_alias():
    guide = (Path(__file__).parents[1] / 'doc/overview.md').read_text()
    example = guide.split('## Endpoint aliases')[1].split('```yaml\n')[1].split('```')[0]
    doc = parse_nodl(example)
    text = render(subscriptions=doc.subscriptions)
    assert 'sub_good_name_' in text
    assert 'on_good_name' in text
    assert '"/whatever/my/topic/is"' in text


@pytest.mark.parametrize('collision', [False, True])
def test_aliases_from_includes(fake_resolver, tmp_path, collision):
    from nodl_generator_cpp.generate import generate_cpp

    ref = fake_resolver.add_text(
        'endpoints',
        yaml.safe_dump({
            'nodl_version': 2,
            'service_clients': [{'name': '/long/name', 'type': 'std_srvs/Trigger', 'alias': 'short'}],
        }),
    )
    data = {'nodl_version': 2, 'include': [{'ref': 'test://rclcpp_node'}, {'ref': ref}]}
    if collision:
        data['service_clients'] = [{'name': '/short', 'type': 'std_srvs/Trigger'}]
    source = tmp_path / 'root.nodl.yaml'
    source.write_text(yaml.safe_dump(data))
    if collision:
        with pytest.raises(ValueError, match='collision.*cli_short_'):
            generate_cpp(source, 'test_base')
    else:
        text = '\n'.join(file.content for file in generate_cpp(source, 'test_base'))
        assert 'cli_short_' in text
        assert '"/long/name"' in text
