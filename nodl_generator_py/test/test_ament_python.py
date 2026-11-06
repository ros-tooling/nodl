# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Tests for the declarations and checks of ``setup.py`` support for ``ament_python`` packages.

The tests of ``test_ament_python_example`` build a package with them.
"""

import shutil
from distutils.command.install_data import install_data
from pathlib import Path

import pytest
import setuptools.command.build_py
import setuptools.command.develop
from marks import SETUPTOOLS_MAJOR, needs_setuptools_lt_80
from setuptools.errors import SetupError

import nodl_generator_py.ament_python
from nodl_generator_py.ament_python import (
    Document,
    _check_runtime_dependency,
    _read_package_name,
    nodl_cmdclass,
    nodl_generate_py,
)

_PACKAGE_XML = """<?xml version="1.0"?>
<package format="3">
  <name>my_robot</name>
  <version>1.0.0</version>
  <description>A robot.</description>
  <maintainer email="a@example.com">A</maintainer>
  <license>Apache-2.0</license>
  {depends}
</package>
"""


def _package_xml(tmp_path: Path, depends: str) -> Path:
    path = tmp_path / 'package.xml'
    path.write_text(_PACKAGE_XML.format(depends=depends))
    return path


def test_declaration_holds_its_arguments():
    assert Document('echo_base', 'nodl/echo.nodl.yaml') == nodl_generate_py('echo_base', 'nodl/echo.nodl.yaml')


@pytest.mark.parametrize('target', ['echo-base', 'class'])
def test_target_must_be_an_identifier_and_not_a_keyword(target):
    with pytest.raises(SetupError, match='nodl_generator_py: target .* is not a valid Python identifier'):
        nodl_generate_py(target, 'echo.nodl.yaml')


def test_document_registers_under_its_target_by_default():
    document = nodl_generate_py('echo_base', 'echo.nodl.yaml')

    assert 'echo_base' == document.resource
    assert not document.no_index


def test_document_registers_under_its_resource_name():
    document = nodl_generate_py('echo_base', 'echo.nodl.yaml', resource_name='echo')

    assert 'echo' == document.resource


def test_resource_name_may_look_false():
    assert 'off' == nodl_generate_py('echo_base', 'echo.nodl.yaml', resource_name='off').resource


@pytest.mark.parametrize(
    ('arguments', 'message'),
    [
        (
            {'no_index': True, 'resource_name': 'echo'},
            "target 'echo_base' is not registered with the ament index because of no_index, "
            "so resource_name 'echo' has no effect. Remove one of them.",
        ),
        ({'resource_name': ''}, "target 'echo_base' has a resource_name with no value"),
        ({'resource_name': 'a/b'}, "target 'echo_base' has a resource_name 'a/b' with a '/'"),
    ],
)
def test_resource_name_is_validated(arguments, message):
    with pytest.raises(SetupError, match=f'nodl_generator_py: {message}'):
        nodl_generate_py('echo_base', 'echo.nodl.yaml', **arguments)


def test_cmdclass_needs_a_document():
    with pytest.raises(SetupError, match='needs at least one document'):
        nodl_cmdclass()


def test_cmdclass_rejects_duplicate_targets():
    documents = [nodl_generate_py('echo_base', 'a.nodl.yaml'), nodl_generate_py('echo_base', 'b.nodl.yaml')]

    with pytest.raises(SetupError, match="target 'echo_base' is declared more than once"):
        nodl_cmdclass(*documents)


def test_cmdclass_rejects_two_documents_with_the_same_resource_name():
    documents = [
        nodl_generate_py('a_base', 'a.nodl.yaml'),
        nodl_generate_py('b_base', 'b.nodl.yaml', resource_name='a_base'),
    ]

    with pytest.raises(SetupError, match="targets 'a_base' and 'b_base' both register the resource name 'a_base'"):
        nodl_cmdclass(*documents)


def test_cmdclass_rejects_two_documents_with_the_same_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    documents = [nodl_generate_py('a_base', 'a.nodl.yaml'), nodl_generate_py('b_base', './sub/../a.nodl.yaml')]

    with pytest.raises(SetupError, match="targets 'a_base' and 'b_base' both register ./sub/../a.nodl.yaml"):
        nodl_cmdclass(*documents)


def test_cmdclass_accepts_unregistered_documents_that_share_a_name_or_a_file():
    documents = [
        nodl_generate_py('a_base', 'a.nodl.yaml'),
        nodl_generate_py('a', 'a.nodl.yaml', no_index=True),
        nodl_generate_py('c_base', 'c.nodl.yaml', resource_name='b_base'),
        nodl_generate_py('b_base', 'a.nodl.yaml', no_index=True),
    ]

    assert nodl_cmdclass(*documents)


def test_cmdclass_wraps_the_setuptools_commands_by_default():
    commands = nodl_cmdclass(nodl_generate_py('echo_base', 'echo.nodl.yaml'))

    assert issubclass(commands['build_py'], setuptools.command.build_py.build_py)
    assert issubclass(commands['install_data'], install_data)


@needs_setuptools_lt_80
def test_cmdclass_wraps_develop():
    commands = nodl_cmdclass(nodl_generate_py('echo_base', 'echo.nodl.yaml'))

    assert issubclass(commands['develop'], setuptools.command.develop.develop)


@pytest.mark.skipif(SETUPTOOLS_MAJOR < 80, reason='before setuptools 80, develop has its own options')
def test_cmdclass_leaves_the_develop_stub_alone():
    commands = nodl_cmdclass(nodl_generate_py('echo_base', 'echo.nodl.yaml'))

    assert 'develop' not in commands


class _EntryPoint:
    def __init__(self, load):
        self.load = load


class _SymlinkData(install_data):
    pass


def _entry_points(monkeypatch, *entries):
    monkeypatch.setattr(nodl_generator_py.ament_python, 'entry_points', lambda **_: list(entries))


def test_cmdclass_wraps_the_symlink_data_command_of_colcon_when_it_is_installed(monkeypatch):
    _entry_points(monkeypatch, _EntryPoint(lambda: _SymlinkData))

    commands = nodl_cmdclass(nodl_generate_py('echo_base', 'echo.nodl.yaml'))

    assert issubclass(commands['symlink_data'], _SymlinkData)
    assert _SymlinkData is not commands['symlink_data']


def test_cmdclass_has_no_symlink_data_command_without_colcon(monkeypatch):
    _entry_points(monkeypatch)

    assert 'symlink_data' not in nodl_cmdclass(nodl_generate_py('echo_base', 'echo.nodl.yaml'))


def test_cmdclass_has_no_symlink_data_command_when_colcon_cannot_be_imported(monkeypatch):
    def load():
        raise ImportError

    _entry_points(monkeypatch, _EntryPoint(load))

    assert 'symlink_data' not in nodl_cmdclass(nodl_generate_py('echo_base', 'echo.nodl.yaml'))


def test_cmdclass_wraps_the_commands_it_is_given_and_keeps_the_others():
    class MyBuildPy(setuptools.command.build_py.build_py):
        pass

    class MySdist:
        pass

    commands = nodl_cmdclass(
        nodl_generate_py('echo_base', 'echo.nodl.yaml'), cmdclass={'build_py': MyBuildPy, 'sdist': MySdist}
    )

    assert issubclass(commands['build_py'], MyBuildPy)
    assert MySdist is commands['sdist']


def test_package_name_is_read_from_package_xml(tmp_path):
    assert 'my_robot' == _read_package_name(_package_xml(tmp_path, ''))


def test_runtime_dependency_passes_when_declared(tmp_path):
    _check_runtime_dependency(_package_xml(tmp_path, '<exec_depend>nodl_runtime_py</exec_depend>'))


@pytest.mark.parametrize(
    'depends',
    [
        '',
        '<build_depend>nodl_runtime_py</build_depend>',
        '<exec_depend condition="$NODL_TEST_ENABLED == 1">nodl_runtime_py</exec_depend>',
    ],
)
def test_runtime_dependency_is_required(tmp_path, monkeypatch, depends):
    monkeypatch.setenv('NODL_TEST_ENABLED', '0')

    with pytest.raises(SetupError, match="'my_robot' must declare a runtime dependency on nodl_runtime_py"):
        _check_runtime_dependency(_package_xml(tmp_path, depends))


def test_runtime_dependency_condition_is_evaluated(tmp_path, monkeypatch):
    monkeypatch.setenv('NODL_TEST_ENABLED', '1')
    path = _package_xml(tmp_path, '<exec_depend condition="$NODL_TEST_ENABLED == 1">nodl_runtime_py</exec_depend>')

    _check_runtime_dependency(path)


@pytest.mark.parametrize('content', [None, 'not xml'])
def test_runtime_dependency_needs_a_readable_package_xml(tmp_path, content):
    path = tmp_path / 'package.xml'
    if content is not None:
        path.write_text(content)

    with pytest.raises(SetupError, match='nodl_generator_py: cannot read .*package.xml'):
        _check_runtime_dependency(path)


def test_get_outputs_before_run_declares_the_generated_package_once(tmp_path, monkeypatch):
    package = tmp_path / 'my_robot'
    package.mkdir()
    (package / '__init__.py').touch()
    (tmp_path / 'build' / 'nodl_generated' / 'my_robot' / 'py').mkdir(parents=True)
    _package_xml(tmp_path, '<exec_depend>nodl_runtime_py</exec_depend>')
    shutil.copy(Path(__file__).parent / 'fixtures' / 'interfaces_node.nodl.yaml', tmp_path / 'echo.nodl.yaml')
    monkeypatch.chdir(tmp_path)
    distribution = setuptools.Distribution({
        'script_name': 'setup.py',
        'name': 'my_robot',
        'packages': ['my_robot'],
        'data_files': [('share/my_robot', ['package.xml'])],
        'cmdclass': nodl_cmdclass(nodl_generate_py('echo_base', 'echo.nodl.yaml')),
    })
    build_py = distribution.get_command_obj('build_py')
    build_py.ensure_finalized()

    build_py.get_outputs()
    build_py.run()

    assert ['my_robot', 'nodl_generated.my_robot'] == build_py.packages


def test_build_fails_when_setup_lists_no_package_or_module(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    distribution = setuptools.Distribution({
        'script_name': 'setup.py',
        'name': 'my_robot',
        'cmdclass': nodl_cmdclass(nodl_generate_py('echo_base', 'echo.nodl.yaml')),
    })
    build = distribution.get_command_obj('build')
    build.ensure_finalized()

    with pytest.raises(SetupError, match=r'nodl_generator_py: setup\(\) must list a package or module'):
        build.run()
