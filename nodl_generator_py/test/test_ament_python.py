# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Tests for the declarations and checks of ``setup.py`` support for ``ament_python`` packages.

The tests of ``test_ament_python_example`` build a package with them.
"""

import shutil
from pathlib import Path

import pytest
import setuptools.command.build_py
import setuptools.command.develop
from setuptools.errors import SetupError

from nodl_generator_py.ament_python import (
    Document,
    _check_package,
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


def test_cmdclass_needs_a_document():
    with pytest.raises(SetupError, match='needs at least one document'):
        nodl_cmdclass()


def test_cmdclass_rejects_duplicate_targets():
    documents = [nodl_generate_py('echo_base', 'a.nodl.yaml'), nodl_generate_py('echo_base', 'b.nodl.yaml')]

    with pytest.raises(SetupError, match="target 'echo_base' is declared more than once"):
        nodl_cmdclass(*documents)


def test_cmdclass_wraps_the_setuptools_commands_by_default():
    commands = nodl_cmdclass(nodl_generate_py('echo_base', 'echo.nodl.yaml'))

    assert issubclass(commands['build_py'], setuptools.command.build_py.build_py)
    assert issubclass(commands['develop'], setuptools.command.develop.develop)


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


def test_package_must_be_listed():
    with pytest.raises(SetupError, match="does not list the package 'my_robot'"):
        _check_package('my_robot', ['other'], {})


@pytest.mark.parametrize(
    ('packages', 'package_dir', 'existing_dir'),
    [
        (['my_robot', 'my_robot.generated'], {}, None),
        (['my_robot'], {}, 'my_robot/generated'),
        (['my_robot'], {'': 'src'}, 'src/my_robot/generated'),
    ],
)
def test_package_must_not_have_a_generated_subpackage(tmp_path, monkeypatch, packages, package_dir, existing_dir):
    monkeypatch.chdir(tmp_path)
    if existing_dir is not None:
        (tmp_path / existing_dir).mkdir(parents=True)

    with pytest.raises(SetupError, match="already has a 'generated' subpackage"):
        _check_package('my_robot', packages, package_dir)


def test_package_without_a_generated_subpackage_passes(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / 'my_robot').mkdir()

    _check_package('my_robot', ['my_robot'], {})


def test_get_outputs_before_run_does_not_make_the_generated_package_a_conflict(tmp_path, monkeypatch):
    package = tmp_path / 'my_robot'
    package.mkdir()
    (package / '__init__.py').touch()
    (tmp_path / 'build' / 'nodl_generated' / 'my_robot' / 'generated').mkdir(parents=True)
    _package_xml(tmp_path, '<exec_depend>nodl_runtime_py</exec_depend>')
    shutil.copy(Path(__file__).parent / 'fixtures' / 'interfaces_node.nodl.yaml', tmp_path / 'echo.nodl.yaml')
    monkeypatch.chdir(tmp_path)
    distribution = setuptools.Distribution({
        'script_name': 'setup.py',
        'name': 'my_robot',
        'packages': ['my_robot'],
        'cmdclass': nodl_cmdclass(nodl_generate_py('echo_base', 'echo.nodl.yaml')),
    })
    build_py = distribution.get_command_obj('build_py')
    build_py.ensure_finalized()

    build_py.get_outputs()
    build_py.run()

    assert ['my_robot', 'my_robot.generated'] == build_py.packages
