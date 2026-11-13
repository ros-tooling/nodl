# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Callback-group syntax, ownership, and both generator entry points."""

import pytest
import yaml
from jsonschema import ValidationError

from nodl_generator_common.plan import CodegenError
from nodl_generator_cpp.cli import main
from nodl_generator_cpp.generate import CODEGEN_CPP_SCHEMA, cmake_deps, generate_cpp


def _source(tmp_path, groups, *, subscriptions=('image',), services=('status',), includes=()):
    document = {
        'nodl_version': 2,
        'include': [{'ref': ref} for ref in ('test://rclcpp_node', *includes)],
        'codegen': {'cpp': {'role': 'NODE', 'callback_groups': groups}},
        'subscriptions': [
            {
                'name': name,
                'type': 'std_msgs/msg/Empty',
                'qos': {'history': 'KEEP_LAST', 'depth': 1, 'reliability': 'RELIABLE'},
            }
            for name in subscriptions
        ],
        'service_servers': [{'name': name, 'type': 'std_srvs/srv/Trigger'} for name in services],
    }
    path = tmp_path / 'node.nodl.yaml'
    path.write_text(yaml.safe_dump(document))
    return path


def _group(**assignments):
    return {'type': 'MUTUALLY_EXCLUSIVE', **assignments}


@pytest.mark.parametrize('kind', ['MUTUALLY_EXCLUSIVE', 'REENTRANT'])
def test_both_group_types(kind):
    config = CODEGEN_CPP_SCHEMA.load({
        'cpp': {'role': 'NODE', 'callback_groups': {'work': {'type': kind, 'subscriptions': ['image']}}}
    })
    assert config.callback_groups['work'].type.value == kind


@pytest.mark.parametrize('name', ['', '_work', 'Work', 'work-group', '1work', 'work/name'])
def test_invalid_group_identifiers(name):
    with pytest.raises(ValidationError):
        CODEGEN_CPP_SCHEMA.load({'cpp': {'role': 'NODE', 'callback_groups': {name: _group(subscriptions=['image'])}}})


@pytest.mark.parametrize(
    'group',
    [
        {},
        {'type': 'REENTRANT'},
        {'type': 'OTHER', 'subscriptions': ['image']},
        _group(subscriptions=[]),
        _group(subscriptions=['image', 'image']),
        _group(service_servers=['status', 'status']),
        _group(service_clients=['client']),
        _group(action_servers=['action']),
        _group(publishers=['image']),
        _group(subscriptions=[1]),
        _group(subscriptions=['image'], extra=True),
    ],
)
def test_invalid_group_shapes(group):
    with pytest.raises(ValidationError):
        CODEGEN_CPP_SCHEMA.load({'cpp': {'role': 'NODE', 'callback_groups': {'work': group}}})


@pytest.mark.parametrize('role', ['BASE_CLASS', 'NO_GENERATE'])
def test_groups_only_on_root_node(role):
    config = {'role': role, 'callback_groups': {'work': _group(subscriptions=['image'])}}
    if role == 'BASE_CLASS':
        config.update({'class': 'rclcpp::Node', 'header': 'rclcpp/rclcpp.hpp'})
    with pytest.raises(ValidationError, match='callback_groups'):
        CODEGEN_CPP_SCHEMA.load({'cpp': config})


@pytest.mark.parametrize('entry', [generate_cpp, cmake_deps])
@pytest.mark.parametrize(
    'groups,detail',
    [
        ({'work': _group(subscriptions=['absent'])}, "subscriptions endpoint 'absent'"),
        ({'work': _group(service_servers=['absent'])}, "service_servers endpoint 'absent'"),
        ({'first': _group(subscriptions=['image']), 'second': _group(subscriptions=['image'])}, 'already assigned'),
        ({'work': _group(subscriptions=['/image'])}, "subscriptions endpoint '/image'"),
        ({'work': _group(subscriptions=['~/image'])}, "subscriptions endpoint '~/image'"),
    ],
)
def test_both_entry_points_validate_assignments(fake_resolver, tmp_path, entry, groups, detail):
    source = _source(tmp_path, groups)
    with pytest.raises(CodegenError, match=detail):
        entry(source, 'node_base')


@pytest.mark.parametrize('mode', [[], ['--cmake-deps']])
def test_cli_does_not_write_on_assignment_error(fake_resolver, tmp_path, mode, capsys):
    source = _source(tmp_path, {'work': _group(subscriptions=['absent'])})
    output = tmp_path / 'output'
    assert main(['--nodl-file', str(source), '--output-dir', str(output), '--target-name', 'node_base', *mode]) == 1
    assert not output.exists()
    assert "callback group 'work': subscriptions endpoint 'absent'" in capsys.readouterr().err


@pytest.mark.parametrize('name', ['image', '/image', '~/image'])
def test_exact_endpoint_names(fake_resolver, tmp_path, name):
    source = _source(tmp_path, {'work': _group(subscriptions=[name])}, subscriptions=(name,))
    assert generate_cpp(source, 'node_base')
    assert cmake_deps(source, 'node_base')


def test_same_name_in_different_categories(fake_resolver, tmp_path):
    source = _source(
        tmp_path,
        {
            'work': _group(subscriptions=['image']),
            'control': _group(service_servers=['image']),
        },
        services=('image',),
    )
    assert generate_cpp(source, 'node_base')


@pytest.mark.parametrize('role', [None, 'BASE_CLASS', 'NO_GENERATE'])
@pytest.mark.parametrize('entry', [generate_cpp, cmake_deps])
def test_include_ownership(fake_resolver, tmp_path, role, entry):
    child = {
        'nodl_version': 2,
        'subscriptions': [
            {
                'name': 'included',
                'type': 'std_msgs/msg/Empty',
                'qos': {'history': 'KEEP_LAST', 'depth': 1, 'reliability': 'RELIABLE'},
            }
        ],
    }
    if role:
        metadata = {'role': role}
        if role == 'BASE_CLASS':
            metadata.update({'class': 'rclcpp::Node', 'header': 'rclcpp/rclcpp.hpp'})
        child['codegen'] = {'cpp': metadata}
    ref = fake_resolver.add_text('child', yaml.safe_dump(child))
    source = _source(tmp_path, {'work': _group(subscriptions=['included'])}, includes=(ref,))
    if role == 'BASE_CLASS':
        document = yaml.safe_load(source.read_text())
        document['include'] = [{'ref': ref}]
        source.write_text(yaml.safe_dump(document))
    if role:
        with pytest.raises(CodegenError, match="subscriptions endpoint 'included' is not generated"):
            entry(source, 'node_base')
    else:
        assert entry(source, 'node_base')


def test_empty_map_preserves_default_output(fake_resolver, tmp_path):
    source = _source(tmp_path, {})
    with_empty = generate_cpp(source, 'node_base')
    document = yaml.safe_load(source.read_text())
    del document['codegen']['cpp']['callback_groups']
    source.write_text(yaml.safe_dump(document))
    assert generate_cpp(source, 'node_base') == with_empty
