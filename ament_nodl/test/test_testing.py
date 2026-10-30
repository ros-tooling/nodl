# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""The arguments, defaults and launch description of ``conformance_test``, with no ROS graph."""

import unittest

import pytest
from launch_testing.actions import ReadyToTest

from ament_nodl import testing
from nodl_schema import IgnoreRule, composition


@pytest.fixture
def document(tmp_path):
    path = tmp_path / 'node.nodl.yaml'
    path.write_text('nodl_version: 2\n', encoding='utf-8')
    return path


@pytest.fixture
def recorded(monkeypatch):
    """Record the ``Node`` and ``assert_conforms`` calls, which the launch description and the test case make."""
    calls = {'node': [], 'assert_conforms': []}
    monkeypatch.setattr(testing, 'Node', lambda **kwargs: calls['node'].append(kwargs) or kwargs)
    monkeypatch.setattr(testing, 'assert_conforms', lambda **kwargs: calls['assert_conforms'].append(kwargs))
    return calls


def _run_test_case(test_case):
    test_case('test_conformance').test_conformance()


def test_returns_what_launch_testing_collects(document):
    generate_test_description, test_case = testing.conformance_test(package='pkg', executable='node_exe', nodl=document)

    assert [mark.name for mark in generate_test_description.pytestmark] == ['launch_test']
    assert issubclass(test_case, unittest.TestCase)
    assert test_case.__name__ == 'TestNodlConformance'


def test_defaults_match_the_cmake_macro(document, recorded, monkeypatch):
    monkeypatch.delenv('NODL_CONFORMANCE_IGNORE', raising=False)
    generate_test_description, test_case = testing.conformance_test(package='pkg', executable='node_exe', nodl=document)

    description = generate_test_description()
    _run_test_case(test_case)

    assert recorded['node'] == [
        {
            'package': 'pkg',
            'executable': 'node_exe',
            'name': 'node_exe',
            'namespace': '/',
            'output': 'screen',
            'ros_arguments': None,
        }
    ]
    assert isinstance(description.entities[-1], ReadyToTest)
    assert recorded['assert_conforms'] == [
        {'nodl_file': str(document), 'node_fqn': '/node_exe', 'timeout_sec': 15, 'ignore': []}
    ]


def test_passes_every_option(document, tmp_path, recorded, monkeypatch):
    monkeypatch.setenv('NODL_CONFORMANCE_IGNORE', 'publisher:/topic_statistics  parameter:use_sim_time')
    first = tmp_path / 'first.yaml'
    second = tmp_path / 'second.yaml'
    first.write_text('{}\n', encoding='utf-8')
    second.write_text('{}\n', encoding='utf-8')
    generate_test_description, test_case = testing.conformance_test(
        package='pkg',
        executable='node-exe',
        nodl=str(document),
        node_name='fixture',
        node_namespace='/robot/',
        timeout=40,
        parameters=['limit:=5', 'path:=a:=b'],
        parameters_files=[first, str(second)],
        ignore=['subscription:/it/*'],
    )

    generate_test_description()
    _run_test_case(test_case)

    node = recorded['node'][0]
    assert (node['name'], node['namespace']) == ('fixture', '/robot/')
    assert node['ros_arguments'] == [
        '--params-file',
        str(first),
        '--params-file',
        str(second),
        '-p',
        'limit:=5',
        '-p',
        'path:=a:=b',
    ]
    assert recorded['assert_conforms'] == [
        {
            'nodl_file': str(document),
            'node_fqn': '/robot/fixture',
            'timeout_sec': 40,
            'ignore': [
                IgnoreRule.parse('subscription:/it/*'),
                'publisher:/topic_statistics',
                'parameter:use_sim_time',
            ],
        }
    ]


def test_resolves_a_reference_with_the_registered_resolvers(tmp_path, recorded):
    registered = tmp_path / 'registered'
    registered.write_text('nodl_version: 2\n', encoding='utf-8')

    class Resolver(composition.Resolver):
        def handles(self, ref):
            return ref.startswith('nodl-test://')

        def resolve(self, ref, origin=None):
            return registered

    with composition.resolver_registered(Resolver()):
        _, test_case = testing.conformance_test(package='pkg', executable='node_exe', nodl='nodl-test://other/my_node')
    _run_test_case(test_case)

    assert recorded['assert_conforms'][0]['nodl_file'] == str(registered)


def test_rejects_an_unregistered_reference():
    with pytest.raises(composition.ResolutionError, match='pkg_that_is_not_installed__my_node'):
        testing.conformance_test(package='pkg', executable='node_exe', nodl='nodl://pkg_that_is_not_installed/my_node')


def test_treats_an_unhandled_scheme_as_a_path():
    with pytest.raises(ValueError, match='must be absolute'):
        testing.conformance_test(package='pkg', executable='node_exe', nodl='unknown://pkg/my_node')


def test_rejects_a_missing_document(tmp_path):
    with pytest.raises(FileNotFoundError, match='missing.nodl.yaml'):
        testing.conformance_test(package='pkg', executable='node_exe', nodl=tmp_path / 'missing.nodl.yaml')


def test_rejects_a_relative_document():
    with pytest.raises(ValueError, match='must be absolute'):
        testing.conformance_test(package='pkg', executable='node_exe', nodl='node.nodl.yaml')


def test_rejects_a_missing_parameters_file(document, tmp_path):
    with pytest.raises(FileNotFoundError, match='missing.yaml'):
        testing.conformance_test(
            package='pkg', executable='node_exe', nodl=document, parameters_files=[tmp_path / 'missing.yaml']
        )


def test_rejects_an_executable_that_is_not_a_node_name(document):
    with pytest.raises(ValueError, match="'node-exe' is not a valid node name, pass node_name"):
        testing.conformance_test(package='pkg', executable='node-exe', nodl=document)


@pytest.mark.parametrize('timeout', [0, -1, 1.5, '15', True])
def test_rejects_an_invalid_timeout(document, timeout):
    with pytest.raises(ValueError, match='timeout must be a positive integer'):
        testing.conformance_test(package='pkg', executable='node_exe', nodl=document, timeout=timeout)


@pytest.mark.parametrize('item', ['no_separator', ':=value', 'name=value', 'name:='])
def test_rejects_an_invalid_parameter_item(document, item):
    with pytest.raises(ValueError, match='parameters item must be name:=value'):
        testing.conformance_test(package='pkg', executable='node_exe', nodl=document, parameters=['ok:=1', item])


def test_rejects_an_invalid_ignore_rule(document):
    with pytest.raises(ValueError, match='KIND:NAME'):
        testing.conformance_test(package='pkg', executable='node_exe', nodl=document, ignore=['publisher'])


def test_an_empty_namespace_is_the_root_namespace(document, recorded):
    generate_test_description, test_case = testing.conformance_test(
        package='pkg', executable='node_exe', nodl=document, node_namespace=''
    )

    generate_test_description()
    _run_test_case(test_case)

    assert recorded['node'][0]['namespace'] == '/'
    assert recorded['assert_conforms'][0]['node_fqn'] == '/node_exe'


def test_the_test_case_belongs_to_the_calling_module(document):
    generate_test_description, test_case = testing.conformance_test(package='pkg', executable='node_exe', nodl=document)

    assert test_case.__module__ == __name__
    assert generate_test_description.__module__ == __name__
    assert test_case.__qualname__ == 'TestNodlConformance'


@pytest.mark.parametrize('option', ['parameters', 'parameters_files', 'ignore'])
def test_rejects_one_string_for_a_list(document, option):
    with pytest.raises(TypeError, match=f'{option} must be a list of strings'):
        testing.conformance_test(package='pkg', executable='node_exe', nodl=document, **{option: 'a:=1'})
