# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Tests for the setuptools extension that generates NoDL nodes for ``ament_python`` packages.

The parsing tests call the extension's functions.
The build tests run ``setup.py`` and ``pip`` in a small project, which needs ``nodl_generator_py`` installed so that setuptools finds the extension.
Where the build tests install to is not a default of the distribution's Python,
so they look for the installed files instead of at fixed paths.
"""

import configparser
import importlib.metadata
import importlib.util
import os
import shutil
import stat
import subprocess
import sys
import zipfile
from distutils.errors import DistutilsSetupError
from pathlib import Path

import pytest
import setuptools
import setuptools.command.build_py
import setuptools.command.install
import setuptools.dist

from nodl_generator_py.setuptools_plugin import (
    Config,
    Document,
    Executable,
    check_runtime_dependency,
    parse_config,
    project_dir,
)

_FIXTURES = Path(__file__).parent / 'fixtures'


def _options(**sections: dict[str, str]) -> dict:
    """Shape sections as ``Distribution.command_options`` holds them, with section names given as ``nodl_generate_py__x``."""
    return {
        name.replace('__', '.'): {key: ('setup.cfg', value) for key, value in options.items()}
        for name, options in sections.items()
    }


def _raw_options(sections: dict[str, dict[str, str]]) -> dict:
    return {name: {key: ('setup.cfg', value) for key, value in section.items()} for name, section in sections.items()}


def test_no_sections_is_no_configuration():
    assert Config((), ()) == parse_config({'metadata': {'name': ('setup.cfg', 'my_robot')}})


def test_document_defaults_to_registering_under_its_target():
    config = parse_config(_options(nodl_generate_py__echo_base={'nodl_file': 'nodl/echo.nodl.yaml'}))

    assert (Document('echo_base', 'nodl/echo.nodl.yaml', None, True),) == config.documents
    assert 'echo_base' == config.documents[0].resource


def test_document_options_are_read():
    config = parse_config(
        _options(
            nodl_generate_py__echo_base={'nodl_file': 'nodl/echo.nodl.yaml', 'resource_name': 'echo'},
            nodl_generate_py__other_base={'nodl_file': 'nodl/echo.nodl.yaml', 'no_index': 'True'},
        )
    )

    assert (
        Document('echo_base', 'nodl/echo.nodl.yaml', 'echo', True),
        Document('other_base', 'nodl/echo.nodl.yaml', None, False),
    ) == config.documents
    assert 'echo' == config.documents[0].resource


@pytest.mark.parametrize(
    ('value', 'index'),
    [
        ('true', False),
        ('yes', False),
        ('on', False),
        ('1', False),
        ('false', True),
        ('no', True),
        ('off', True),
        ('0', True),
    ],
)
def test_no_index_accepts_the_usual_booleans(value, index):
    config = parse_config(_options(nodl_generate_py__echo_base={'nodl_file': 'echo.nodl.yaml', 'no_index': value}))

    assert index == config.documents[0].index


def test_resource_name_may_look_false():
    config = parse_config(_options(nodl_generate_py__echo_base={'nodl_file': 'echo.nodl.yaml', 'resource_name': 'off'}))

    assert 'off' == config.documents[0].resource


def test_executable_options_are_read():
    config = parse_config(
        _options(
            nodl_add_py_executable__echo={'target': 'my_robot.echo:Echo'},
            nodl_add_py_executable__threaded={
                'target': 'my_robot.echo:Echo',
                'executor': 'rclpy.executors:MultiThreadedExecutor',
            },
        )
    )

    assert (
        Executable('echo', 'my_robot.echo:Echo', None),
        Executable('threaded', 'my_robot.echo:Echo', 'rclpy.executors:MultiThreadedExecutor'),
    ) == config.executables


def test_executable_name_may_contain_a_dot():
    options = {'nodl_add_py_executable.echo.py': {'target': ('setup.cfg', 'my_robot.echo:Echo')}}

    assert 'echo.py' == parse_config(options).executables[0].name


@pytest.mark.parametrize(
    ('sections', 'expected'),
    [
        ({'nodl_generate_py.echo_base': {}}, '[nodl_generate_py.echo_base] needs the option nodl_file'),
        (
            {'nodl_generate_py.echo_base': {'nodl_file': 'a.yaml', 'file': 'b'}},
            "[nodl_generate_py.echo_base] has unknown option 'file', expected one of: nodl_file, resource_name, no_index",
        ),
        (
            {'nodl_generate_py.echo_base': {'nodl_file': 'a.yaml', 'resource_name': ''}},
            '[nodl_generate_py.echo_base] has an option resource_name with no value',
        ),
        ({'nodl_generate_py.echo_base': {'nodl_file': ''}}, 'has an option nodl_file with no value'),
        (
            {'nodl_generate_py.echo_base': {'nodl_file': 'a.yaml', 'no_index': 'maybe'}},
            "option no_index is 'maybe', expected true or false",
        ),
        (
            {'nodl_generate_py.echo_base': {'nodl_file': 'a.yaml', 'no_index': 'true', 'resource_name': 'echo'}},
            "not registered with the ament index because of no_index, so resource_name 'echo' has no effect. Remove one of them.",
        ),
        (
            {'nodl_generate_py.echo_base': {'nodl_file': 'a.yaml', 'resource_name': 'a/b'}},
            "resource_name 'a/b' must not contain '/'",
        ),
        (
            {'nodl_generate_py.echo-base': {'nodl_file': 'a.yaml'}},
            "target 'echo-base' is not a valid Python identifier",
        ),
        ({'nodl_generate_py.class': {'nodl_file': 'a.yaml'}}, "target 'class' is not a valid Python identifier"),
        (
            {
                'nodl_generate_py.a_base': {'nodl_file': 'a.yaml'},
                'nodl_generate_py.b_base': {'nodl_file': 'b.yaml', 'resource_name': 'a_base'},
            },
            "documents 'a_base' and 'b_base' both register the resource name 'a_base'",
        ),
        (
            {'nodl_generate_py': {'nodl_file': 'a.yaml'}},
            '[nodl_generate_py] needs a name, as in [nodl_generate_py.<name>]',
        ),
        ({'nodl_generate_py.': {'nodl_file': 'a.yaml'}}, '[nodl_generate_py.] needs a name'),
        (
            {'nodl_add_py_executable': {'target': 'm:C'}},
            '[nodl_add_py_executable] needs a name, as in [nodl_add_py_executable.<name>]',
        ),
        ({'nodl_add_py_executable.echo': {}}, '[nodl_add_py_executable.echo] needs the option target'),
        (
            {'nodl_add_py_executable.echo': {'target': 'my_robot.echo:Echo', 'node': 'x'}},
            "has unknown option 'node', expected one of: target, executor",
        ),
        ({'nodl_add_py_executable.a/b': {'target': 'm:C'}}, "executable name 'a/b' must not contain '/'"),
    ],
)
def test_invalid_configuration_is_rejected(sections, expected):
    with pytest.raises(DistutilsSetupError) as error:
        parse_config(_raw_options(sections))

    assert expected in ' '.join(str(error.value).split())


def test_documents_may_share_a_file_when_only_one_is_registered():
    config = parse_config(
        _options(
            nodl_generate_py__a_base={'nodl_file': 'a.yaml'},
            nodl_generate_py__b_base={'nodl_file': 'a.yaml', 'no_index': 'true'},
        )
    )

    assert 2 == len(config.documents)


def test_project_dir_is_where_setup_cfg_really_is(tmp_path):
    (tmp_path / 'src').mkdir()
    (tmp_path / 'src' / 'setup.cfg').touch()
    (tmp_path / 'build').mkdir()
    (tmp_path / 'build' / 'setup.cfg').symlink_to(tmp_path / 'src' / 'setup.cfg')
    options = {
        'nodl_generate_py.a_base': {'nodl_file': (str(tmp_path / 'build' / 'setup.cfg'), 'a.yaml')},
        'metadata': {'name': ('elsewhere.cfg', 'my_robot')},
    }

    assert (tmp_path / 'src').resolve() == project_dir(options)


@pytest.mark.parametrize(
    'sources',
    [['setup.py'], ['setup.cfg', 'other/setup.cfg'], ['~/.pydistutils.cfg']],
    ids=['not-setup-cfg', 'two-files', 'user-config'],
)
def test_project_dir_rejects_sections_from_anywhere_else(sources):
    options = {f'nodl_generate_py.t{index}': {'nodl_file': (source, 'a.yaml')} for index, source in enumerate(sources)}

    with pytest.raises(DistutilsSetupError, match='must all be in one setup.cfg'):
        project_dir(options)


def _package_xml(directory: Path, dependencies: str) -> Path:
    path = directory / 'package.xml'
    path.write_text(
        f"""\
<?xml version="1.0"?>
<package format="3">
  <name>my_robot</name>
  <version>0.0.0</version>
  <description>Package.</description>
  <maintainer email="test@example.com">test</maintainer>
  <license>Apache-2.0</license>
  {dependencies}
</package>
"""
    )
    return path


@pytest.mark.parametrize(
    'dependency',
    [
        '<exec_depend>nodl_runtime_py</exec_depend>',
        '<depend>nodl_runtime_py</depend>',
        '<exec_depend condition="1 == 1">nodl_runtime_py</exec_depend>',
    ],
)
def test_declared_runtime_dependency_returns_the_package_name(tmp_path, dependency):
    assert 'my_robot' == check_runtime_dependency(_package_xml(tmp_path, dependency))


@pytest.mark.parametrize(
    'dependency',
    [
        '',
        '<build_depend>nodl_runtime_py</build_depend>',
        '<test_depend>nodl_runtime_py</test_depend>',
        '<exec_depend condition="1 == 0">nodl_runtime_py</exec_depend>',
    ],
)
def test_missing_runtime_dependency_is_rejected(tmp_path, dependency):
    with pytest.raises(DistutilsSetupError) as error:
        check_runtime_dependency(_package_xml(tmp_path, dependency))

    message = ' '.join(str(error.value).split())
    assert "package 'my_robot' must declare a runtime dependency on nodl_runtime_py" in message
    assert 'Add <exec_depend>nodl_runtime_py</exec_depend> to its package.xml.' in message


def test_unreadable_package_xml_is_rejected(tmp_path):
    with pytest.raises(DistutilsSetupError, match='cannot read'):
        check_runtime_dependency(tmp_path / 'package.xml')


def test_documented_example_configuration_parses():
    example = Path(__file__).parent.parent / 'doc' / 'examples' / 'echo_robot_py' / 'setup.cfg'
    parser = configparser.ConfigParser()
    parser.optionxform = str
    parser.read(example)

    config = parse_config(_raw_options({section: dict(parser[section]) for section in parser.sections()}))

    assert (Document('echo_node_base', 'nodl/echo_node.nodl.yaml', None, True),) == config.documents
    assert (Executable('echo_node', 'echo_robot_py.echo_node:EchoNode', None),) == config.executables


SETUP_PY = """\
from setuptools import setup

setup(
    name="my_robot",
    version="0.0.0",
    packages=["my_robot"],
    {package_dir}
    data_files=[("share/my_robot", ["package.xml"])],
)
"""

SETUP_CFG = """
[nodl_generate_py.echo_base]
nodl_file = nodl/echo.nodl.yaml

[nodl_generate_py.hidden_base]
nodl_file = nodl/echo.nodl.yaml
no_index = true

[nodl_generate_py.composed_base]
nodl_file = nodl/composed.nodl.yaml
resource_name = composed

[nodl_generate_py.sibling_base]
nodl_file = nodl/sibling.nodl.yaml
resource_name = sibling

[nodl_add_py_executable.echo_node]
target = my_robot.echo:Echo
executor = rclpy.executors:MultiThreadedExecutor
"""

SIBLING = """\
---
nodl_version: 2
publishers:
  - name: /sibling_out
    type: std_msgs/msg/String
    qos:
      history: KEEP_LAST
      depth: 10
      reliability: RELIABLE
"""

COMPOSED = """\
---
nodl_version: 2
include:
  - ref: local://sibling.nodl.yaml
"""

EXEC_DEPEND = '<exec_depend>nodl_runtime_py</exec_depend>'

# Generated by SETUP_CFG, as paths that end the installed files'.
EXPECTED = [
    'my_robot/generated/__init__.py',
    'my_robot/generated/echo_base.py',
    'my_robot/generated/echo_base_parameters.py',
    'my_robot/generated/hidden_base.py',
    'my_robot/generated/composed_base.py',
    'my_robot/generated/sibling_base.py',
    'share/ament_index/resource_index/nodl/my_robot__echo_base',
    'share/ament_index/resource_index/nodl/my_robot__composed',
    'share/ament_index/resource_index/nodl/my_robot__sibling',
    'share/my_robot/nodl/echo_base.nodl.yaml',
    'share/my_robot/nodl/composed.nodl.yaml',
    'share/my_robot/nodl/sibling.nodl.yaml',
    'echo_node',
]


def _project(tmp_path: Path, setup_cfg: str = SETUP_CFG, dependencies: str = EXEC_DEPEND, layout: str = 'flat') -> Path:
    """Create a project with the package directly in it, or under ``src`` for the ``src`` layout."""
    project = tmp_path / 'project'
    package = project / 'src' / 'my_robot' if layout == 'src' else project / 'my_robot'
    package.mkdir(parents=True)
    (package / '__init__.py').touch()
    (project / 'nodl').mkdir()
    shutil.copy(_FIXTURES / 'interfaces_node.nodl.yaml', project / 'nodl' / 'echo.nodl.yaml')
    (project / 'nodl' / 'sibling.nodl.yaml').write_text(SIBLING)
    (project / 'nodl' / 'composed.nodl.yaml').write_text(COMPOSED)
    package_dir = 'package_dir={"": "src"},' if layout == 'src' else ''
    (project / 'setup.py').write_text(SETUP_PY.format(package_dir=package_dir))
    (project / 'setup.cfg').write_text(setup_cfg)
    _package_xml(project, dependencies)
    return project


def _run(command, cwd: Path, **environment) -> subprocess.CompletedProcess:
    names = {entry.name for entry in importlib.metadata.entry_points(group='setuptools.finalize_distribution_options')}
    assert 'nodl_generator_py' in names, 'the build tests need nodl_generator_py installed, so setuptools can find it'
    return subprocess.run(
        [str(part) for part in command],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1', **environment},
    )


def _setup(project: Path, *arguments, **environment) -> subprocess.CompletedProcess:
    return _run([sys.executable, 'setup.py', '-q', *arguments], project, **environment)


def _colcon_install(project: Path, tmp_path: Path, root: str = 'root', **environment) -> subprocess.CompletedProcess:
    """Build and install as colcon does for a package that is not a symlink install, keeping the source tree clean."""
    (tmp_path / 'egg').mkdir(exist_ok=True)
    return _setup(
        project,
        'egg_info',
        '--egg-base',
        tmp_path / 'egg',
        'build',
        '--build-base',
        tmp_path / 'build',
        'install',
        '--root',
        tmp_path / root,
        '--single-version-externally-managed',
        '--record',
        tmp_path / 'install.log',
        **environment,
    )


def _installed(root: Path) -> list[str]:
    return sorted(path.relative_to(root).as_posix() for path in root.rglob('*') if path.is_file())


def _find(root: Path, suffix: str) -> Path:
    found = [path for path in root.rglob('*') if path.is_file() and path.as_posix().endswith(f'/{suffix}')]
    assert found, f'{suffix} is not in {_installed(root)}'
    return found[0]


def _assert_installed(root: Path) -> None:
    for suffix in EXPECTED:
        _find(root, suffix)


def _build_then_install(project: Path, tmp_path: Path) -> subprocess.CompletedProcess:
    # The second command finds the first one's build in the default build directory, so work in a copy.
    work = tmp_path / 'work'
    shutil.copytree(project, work)
    result = _setup(work, 'build')
    if result.returncode:
        return result
    return _setup(work, 'install', '--skip-build', '--root', tmp_path / 'root')


def _plain_install(project: Path, tmp_path: Path) -> subprocess.CompletedProcess:
    return _setup(project, 'build', '--build-base', tmp_path / 'build', 'install', '--root', tmp_path / 'root')


def _deb_install(project: Path, tmp_path: Path) -> subprocess.CompletedProcess:
    options = _setup(project, 'install', '--help').stdout
    if '--install-layout' not in options:
        pytest.skip('this setuptools has no Debian install layout')
    return _setup(
        project,
        'build',
        '--build-base',
        tmp_path / 'build',
        'install',
        '--root',
        tmp_path / 'root',
        '--install-layout',
        'deb',
        '--prefix',
        '/usr',
    )


def _wheel(project: Path, tmp_path: Path) -> subprocess.CompletedProcess:
    pytest.importorskip('wheel')
    result = _setup(
        project,
        'bdist_wheel',
        '--dist-dir',
        tmp_path / 'dist',
        '--bdist-dir',
        tmp_path / 'bdist',
        'build',
        '--build-base',
        tmp_path / 'build',
    )
    if result.returncode == 0:
        with zipfile.ZipFile(next((tmp_path / 'dist').glob('*.whl'))) as wheel:
            wheel.extractall(tmp_path / 'root')
    return result


def _pip_install(project: Path, tmp_path: Path) -> subprocess.CompletedProcess:
    pytest.importorskip('pip')
    # pip builds in the source directory, so build in a copy.
    shutil.copytree(project, tmp_path / 'pip_project')
    return _run(
        [
            sys.executable,
            '-m',
            'pip',
            'install',
            '--no-build-isolation',
            '--no-deps',
            '--no-index',
            '--root',
            tmp_path / 'root',
            '.',
        ],
        tmp_path / 'pip_project',
    )


FLOWS = {
    'colcon': lambda project, tmp_path: _colcon_install(project, tmp_path),
    'build-and-install': _plain_install,
    'build-then-install-skip-build': _build_then_install,
    'deb-layout': _deb_install,
    'bdist-wheel': _wheel,
    'pip': _pip_install,
}


@pytest.mark.parametrize('flow', FLOWS.values(), ids=FLOWS.keys())
@pytest.mark.parametrize('layout', ['flat', 'src'])
def test_every_way_of_building_installs_the_generated_files(tmp_path, flow, layout):
    result = flow(_project(tmp_path, layout=layout), tmp_path)

    assert 0 == result.returncode, result.stdout + result.stderr
    _assert_installed(tmp_path / 'root')


def test_installed_documents_have_their_local_includes_rewritten(tmp_path):
    assert 0 == _colcon_install(_project(tmp_path), tmp_path).returncode
    root = tmp_path / 'root'

    composed = _find(root, 'share/ament_index/resource_index/nodl/my_robot__composed').read_text()

    assert 'nodl://my_robot/sibling' in composed
    assert 'local://' not in composed
    assert composed == _find(root, 'share/my_robot/nodl/composed.nodl.yaml').read_text()
    assert not [path for path in _installed(root) if path.endswith('my_robot__hidden_base')]


def test_installed_executable_runs_the_node_class(tmp_path):
    assert 0 == _colcon_install(_project(tmp_path), tmp_path).returncode

    script = _find(tmp_path / 'root', 'echo_node').read_text()

    assert 'from my_robot.echo import Echo' in script
    assert 'run_node(Echo, executor_class=MultiThreadedExecutor)' in script


def test_installed_files_are_recorded(tmp_path):
    assert 0 == _colcon_install(_project(tmp_path), tmp_path).returncode

    recorded = (tmp_path / 'install.log').read_text()

    for suffix in EXPECTED:
        assert f'/{suffix}' in recorded


def _make_read_only(directory: Path) -> None:
    for path in [directory, *directory.rglob('*')]:
        path.chmod(path.stat().st_mode & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))


@pytest.fixture
def writable_at_cleanup(tmp_path):
    yield
    for path in [tmp_path, *tmp_path.rglob('*')]:
        path.chmod(path.stat().st_mode | stat.S_IWUSR)


def test_install_writes_nothing_to_the_source_tree(tmp_path, writable_at_cleanup):
    project = _project(tmp_path)
    before = sorted(path.relative_to(project) for path in project.rglob('*'))
    _make_read_only(project)

    result = _colcon_install(project, tmp_path)

    assert 0 == result.returncode, result.stderr
    assert before == sorted(path.relative_to(project) for path in project.rglob('*'))
    _assert_installed(tmp_path / 'root')


def test_build_writes_nothing_to_the_source_tree(tmp_path, writable_at_cleanup):
    project = _project(tmp_path)
    _make_read_only(project)

    result = _setup(project, 'build', '--build-base', tmp_path / 'build')

    assert 0 == result.returncode, result.stderr
    _find(tmp_path / 'build', 'my_robot/generated/echo_base.py')
    assert not (project / 'build').exists()


def test_a_rebuild_regenerates_an_edited_document(tmp_path):
    project = _project(tmp_path)
    assert 0 == _colcon_install(project, tmp_path, root='first').returncode
    (project / 'nodl' / 'sibling.nodl.yaml').write_text(SIBLING.replace('/sibling_out', '/edited_out'))

    result = _colcon_install(project, tmp_path, root='second')

    assert 0 == result.returncode, result.stderr
    module = _find(tmp_path / 'second', 'my_robot/generated/sibling_base.py').read_text()
    assert '/edited_out' in module
    assert '/sibling_out' not in module


def test_a_rebuild_drops_the_modules_of_a_removed_document(tmp_path):
    project = _project(tmp_path)
    assert 0 == _colcon_install(project, tmp_path, root='first').returncode
    removed = SETUP_CFG.replace(
        '[nodl_generate_py.hidden_base]\nnodl_file = nodl/echo.nodl.yaml\nno_index = true\n', ''
    )
    assert removed != SETUP_CFG
    (project / 'setup.cfg').write_text(removed)

    result = _colcon_install(project, tmp_path, root='second')

    assert 0 == result.returncode, result.stderr
    assert [path for path in _installed(tmp_path / 'first') if path.endswith('hidden_base.py')]
    assert not [path for path in _installed(tmp_path / 'second') if path.endswith('hidden_base.py')]
    _find(tmp_path / 'second', 'my_robot/generated/echo_base.py')


def test_install_without_configuration_changes_nothing(tmp_path):
    project = _project(tmp_path, setup_cfg='[metadata]\nname = my_robot\n', dependencies='')

    result = _colcon_install(project, tmp_path)

    assert 0 == result.returncode, result.stderr
    assert [path for path in _installed(tmp_path / 'root') if 'generated' in path or 'nodl' in path] == []
    assert not (tmp_path / 'build' / 'nodl_generated').exists()


def _fails_with(result: subprocess.CompletedProcess, *messages: str) -> None:
    assert 0 != result.returncode
    output = ' '.join(result.stderr.split())
    for message in messages:
        assert message in output


def test_build_without_the_runtime_dependency_fails(tmp_path):
    result = _colcon_install(_project(tmp_path, dependencies=''), tmp_path)

    _fails_with(result, "package 'my_robot' must declare a runtime dependency on nodl_runtime_py")


def test_build_with_an_unregistered_local_include_fails(tmp_path):
    setup_cfg = SETUP_CFG.replace('resource_name = sibling', 'no_index = true')

    result = _colcon_install(_project(tmp_path, setup_cfg), tmp_path)

    _fails_with(
        result,
        'my_robot__composed includes a local:// reference that is not registered',
        'Register the included file with a nodl_generate_py.<target> section',
    )


def test_build_with_a_file_registered_twice_fails(tmp_path):
    setup_cfg = SETUP_CFG.replace('nodl_file = nodl/echo.nodl.yaml\nno_index = true', 'nodl_file = nodl/echo.nodl.yaml')

    result = _colcon_install(_project(tmp_path, setup_cfg), tmp_path)

    _fails_with(result, 'is already registered as my_robot__echo_base')


def test_build_with_an_invalid_document_names_the_file(tmp_path):
    project = _project(tmp_path)
    (project / 'nodl' / 'echo.nodl.yaml').write_text('nodl_version: 2\npublishers: 3\n')

    result = _colcon_install(project, tmp_path)

    _fails_with(result, 'echo.nodl.yaml')


def test_build_with_a_missing_document_names_the_file(tmp_path):
    project = _project(tmp_path)
    (project / 'nodl' / 'echo.nodl.yaml').unlink()

    result = _colcon_install(project, tmp_path)

    _fails_with(result, 'echo.nodl.yaml')


def test_build_with_an_unexpected_error_keeps_its_traceback(tmp_path):
    project = _project(tmp_path)
    (project / 'setup.py').write_text(
        'import nodl_generator_py.generator as generator\n'
        '\n'
        '\n'
        'def fail(*args):\n'
        '    raise KeyError("unexpected")\n'
        '\n'
        '\n'
        'generator.generate_python = fail\n' + (project / 'setup.py').read_text()
    )

    result = _colcon_install(project, tmp_path)

    assert 0 != result.returncode
    assert "KeyError: 'unexpected'" in result.stderr


def test_build_with_a_bad_executable_reference_fails(tmp_path):
    setup_cfg = SETUP_CFG.replace('target = my_robot.echo:Echo', 'target = my_robot.echo')

    result = _colcon_install(_project(tmp_path, setup_cfg), tmp_path)

    _fails_with(
        result, "[nodl_add_py_executable.echo_node] Node target 'my_robot.echo' is not in the form 'module:Class'"
    )


def test_build_without_the_package_in_setup_fails(tmp_path):
    project = _project(tmp_path)
    (project / 'setup.py').write_text(
        'from setuptools import setup\n\nsetup(name="my_robot", version="0.0.0", packages=[])\n'
    )

    result = _colcon_install(project, tmp_path)

    _fails_with(result, "setup() does not list the package 'my_robot'")


def test_build_with_a_generated_subpackage_of_its_own_fails(tmp_path):
    project = _project(tmp_path)
    (project / 'my_robot' / 'generated').mkdir()
    (project / 'my_robot' / 'generated' / '__init__.py').touch()

    result = _colcon_install(project, tmp_path)

    _fails_with(result, "the package 'my_robot' already has a 'generated' subpackage")


def test_build_with_a_listed_generated_subpackage_fails(tmp_path):
    project = _project(tmp_path)
    setup_py = (project / 'setup.py').read_text()
    (project / 'setup.py').write_text(
        setup_py.replace('packages=["my_robot"]', 'packages=["my_robot", "my_robot.generated"]')
    )

    result = _setup(project, 'build', '--build-base', tmp_path / 'build')

    _fails_with(result, "the package 'my_robot' already has a 'generated' subpackage")


@pytest.mark.parametrize('how', ['entry-point', 'script'])
def test_build_with_a_script_of_the_same_name_fails(tmp_path, how):
    project = _project(tmp_path)
    if how == 'entry-point':
        setup_cfg = SETUP_CFG + '\n[options.entry_points]\nconsole_scripts =\n    echo_node = my_robot:main\n'
        (project / 'setup.cfg').write_text(setup_cfg)
    else:
        (project / 'bin').mkdir()
        (project / 'bin' / 'echo_node').write_text('#!/usr/bin/env python3\n')
        setup_py = (project / 'setup.py').read_text()
        (project / 'setup.py').write_text(setup_py.replace('packages=', 'scripts=["bin/echo_node"], packages='))

    result = _colcon_install(project, tmp_path)

    _fails_with(result, '[nodl_add_py_executable.echo_node] installs a script that the package already installs')


def test_build_with_a_bare_section_fails(tmp_path):
    result = _colcon_install(
        _project(tmp_path, SETUP_CFG + '\n[nodl_generate_py]\nnodl_file = nodl/echo.nodl.yaml\n'), tmp_path
    )

    _fails_with(result, '[nodl_generate_py] needs a name')


def _colcon_build_space(project: Path, tmp_path: Path, layout: str) -> Path:
    """Link the project into a build space as ``colcon build --symlink-install`` does before it runs ``setup.py develop``."""
    build_space = tmp_path / 'build_space'
    package = Path('src') / 'my_robot' if layout == 'src' else Path('my_robot')
    for item in ('setup.py', 'setup.cfg', 'package.xml', package):
        (build_space / item).parent.mkdir(parents=True, exist_ok=True)
        (build_space / item).symlink_to(project / item)
    return build_space


def _colcon_distutils_commands() -> str | None:
    """Return the directory that colcon puts on ``PYTHONPATH`` to give ``setup.py`` its ``symlink_data`` command."""
    spec = importlib.util.find_spec('colcon_core')
    if spec is None or spec.origin is None:
        return None
    commands = Path(spec.origin).parent / 'task' / 'python' / 'colcon_distutils_commands'
    return str(commands) if commands.is_dir() else None


def _develop(build_space: Path, tmp_path: Path, layout: str, data_command: str) -> subprocess.CompletedProcess:
    site = tmp_path / 'site'
    site.mkdir(exist_ok=True)
    python_path = [site, build_space / 'src' if layout == 'src' else build_space, _colcon_distutils_commands()]
    return _run(
        [
            sys.executable,
            'setup.py',
            '-q',
            'develop',
            '--editable',
            '--build-directory',
            build_space / 'build',
            '--no-deps',
            '--install-dir',
            site,
            '--script-dir',
            tmp_path / 'scripts',
            data_command,
            '--install-dir',
            tmp_path / 'data',
        ],
        build_space,
        PYTHONPATH=os.pathsep.join(map(str, filter(None, [*python_path, os.environ.get('PYTHONPATH')]))),
    )


def _python_path(*directories: Path) -> str:
    return os.pathsep.join(filter(None, [*map(str, directories), os.environ.get('PYTHONPATH')]))


def _imports_generated(build_space: Path, layout: str) -> subprocess.CompletedProcess:
    return _run(
        [sys.executable, '-c', 'import my_robot.generated.echo_base_parameters, my_robot.generated.sibling_base'],
        build_space,
        PYTHONPATH=_python_path(build_space / 'src' if layout == 'src' else build_space),
    )


SETUPTOOLS_MAJOR = int(setuptools.__version__.split('.')[0])

needs_develop = pytest.mark.skipif(
    SETUPTOOLS_MAJOR >= 80, reason='from setuptools 80, setup.py develop only runs pip install -e'
)


@needs_develop
@pytest.mark.parametrize('layout', ['flat', 'src'])
@pytest.mark.parametrize('data_command', ['install_data', 'symlink_data'])
def test_develop_in_a_symlink_build_space_makes_the_generated_modules_importable(
    tmp_path, writable_at_cleanup, layout, data_command
):
    if data_command == 'symlink_data' and _colcon_distutils_commands() is None:
        pytest.skip('colcon is not installed')
    project = _project(tmp_path, layout=layout)
    before = sorted(path.relative_to(project) for path in project.rglob('*'))
    _make_read_only(project)
    build_space = _colcon_build_space(project, tmp_path, layout)

    result = _develop(build_space, tmp_path, layout, data_command)

    assert 0 == result.returncode, result.stdout + result.stderr
    imported = _imports_generated(build_space, layout)
    assert 0 == imported.returncode, imported.stderr
    assert before == sorted(path.relative_to(project) for path in project.rglob('*'))
    _find(tmp_path / 'data', 'share/ament_index/resource_index/nodl/my_robot__composed')
    _find(tmp_path / 'data', 'share/my_robot/nodl/sibling.nodl.yaml')
    script = _find(tmp_path / 'scripts', 'echo_node')
    assert 'pkg_resources' not in script.read_text()
    assert 'from my_robot.echo import Echo' in script.read_text()
    assert os.access(script, os.X_OK)


@needs_develop
def test_develop_keeps_edits_to_the_package_and_regenerates_an_edited_document(tmp_path, writable_at_cleanup):
    project = _project(tmp_path)
    build_space = _colcon_build_space(project, tmp_path, 'flat')
    assert 0 == _develop(build_space, tmp_path, 'flat', 'install_data').returncode
    (project / 'my_robot' / 'edited.py').write_text('VALUE = 1\n')
    (project / 'nodl' / 'sibling.nodl.yaml').write_text(SIBLING.replace('/sibling_out', '/edited_out'))
    # colcon links the package again before it runs setup.py develop again.
    shutil.rmtree(build_space / 'my_robot')
    (build_space / 'my_robot').symlink_to(project / 'my_robot')

    result = _develop(build_space, tmp_path, 'flat', 'install_data')

    assert 0 == result.returncode, result.stdout + result.stderr
    code = 'import my_robot.edited, my_robot.generated.sibling_base as m, inspect; assert "/edited_out" in inspect.getsource(m)'
    imported = _run([sys.executable, '-c', code], build_space, PYTHONPATH=_python_path(build_space))
    assert 0 == imported.returncode, imported.stderr


@needs_develop
def test_develop_without_a_symlinked_package_fails(tmp_path):
    project = _project(tmp_path)
    (tmp_path / 'site').mkdir()

    result = _run(
        [
            sys.executable,
            'setup.py',
            '-q',
            'develop',
            '--editable',
            '--build-directory',
            tmp_path / 'build',
            '--no-deps',
            '--install-dir',
            tmp_path / 'site',
            '--script-dir',
            tmp_path / 'scripts',
        ],
        project,
        PYTHONPATH=os.pathsep.join(filter(None, [str(tmp_path / 'site'), os.environ.get('PYTHONPATH')])),
    )

    _fails_with(result, 'setup.py develop needs my_robot to be a symlink to the source package')


@pytest.mark.skipif(SETUPTOOLS_MAJOR < 64, reason='this setuptools has no editable installs')
@pytest.mark.parametrize('read_only', [False, True], ids=['writable', 'read-only'])
def test_editable_pip_install_fails_before_writing_anything(tmp_path, writable_at_cleanup, read_only):
    project = _project(tmp_path)
    before = sorted(path.relative_to(project) for path in project.rglob('*'))
    if read_only:
        _make_read_only(project)

    result = _run(
        [
            sys.executable,
            '-m',
            'pip',
            'install',
            '--use-pep517',
            '--no-build-isolation',
            '--no-deps',
            '--no-index',
            '--prefix',
            tmp_path / 'prefix',
            '-e',
            '.',
        ],
        project,
    )

    assert 0 != result.returncode
    assert 'an editable install cannot import the generated modules' in ' '.join(
        (result.stdout + result.stderr).split()
    )
    assert before == sorted(path.relative_to(project) for path in project.rglob('*') if '__pycache__' not in path.parts)


def test_sections_in_another_configuration_file_fail_clearly(tmp_path):
    project = _project(tmp_path, setup_cfg='[metadata]\nname = my_robot\n')
    (tmp_path / 'home').mkdir()
    (tmp_path / 'home' / '.pydistutils.cfg').write_text(
        '[nodl_generate_py.echo_base]\nnodl_file = nodl/echo.nodl.yaml\n'
    )

    result = _colcon_install(project, tmp_path, HOME=str(tmp_path / 'home'))

    _fails_with(result, 'the nodl_generator_py sections must all be in one setup.cfg', '.pydistutils.cfg')


@pytest.mark.skipif(SETUPTOOLS_MAJOR < 80, reason='before setuptools 80, develop has its own options')
def test_develop_stub_does_not_crash(tmp_path):
    project = _project(tmp_path)

    # It runs pip, which cannot build without an index.
    result = _run(
        [sys.executable, 'setup.py', '-q', 'develop'], project, PIP_NO_INDEX='1', PIP_PREFIX=str(tmp_path / 'prefix')
    )

    assert 'AttributeError' not in result.stderr
    assert 'uninstall' not in result.stderr


def _distribution(tmp_path: Path, monkeypatch, setup_cfg: str, **attributes):
    """Create a distribution in a directory with ``setup.cfg``, which runs the extension's hook."""
    (tmp_path / 'setup.cfg').write_text(setup_cfg)
    monkeypatch.chdir(tmp_path)
    return setuptools.dist.Distribution({'name': 'my_robot', **attributes})


class _OwnBuildPy(setuptools.command.build_py.build_py):
    pass


def test_a_package_without_sections_keeps_its_commands(tmp_path, monkeypatch):
    dist = _distribution(tmp_path, monkeypatch, '[metadata]\nname = my_robot\n', cmdclass={'build_py': _OwnBuildPy})

    assert {'build_py': _OwnBuildPy} == dist.cmdclass
    assert setuptools.command.install.install is dist.get_command_class('install')


@pytest.mark.parametrize(
    'section',
    ['nodl_generate_py.echo_base', 'nodl_generate_py', 'nodl_add_py_executable.echo_node'],
)
def test_a_package_with_a_section_wraps_its_own_commands(tmp_path, monkeypatch, section):
    dist = _distribution(tmp_path, monkeypatch, f'[{section}]\nx = 1\n', cmdclass={'build_py': _OwnBuildPy})

    assert issubclass(dist.cmdclass['build_py'], _OwnBuildPy)
    assert _OwnBuildPy is not dist.cmdclass['build_py']
    assert issubclass(dist.cmdclass['install'], setuptools.command.install.install)


@pytest.mark.parametrize(
    'setup_cfg',
    ['# [nodl_generate_py.echo_base]\n', '[nodl_generate_pyx]\n', '[metadata]\ndescription = [nodl_generate_py.x]\n'],
    ids=['comment', 'other-section', 'value'],
)
def test_text_that_is_not_a_section_wraps_nothing(tmp_path, monkeypatch, setup_cfg):
    dist = _distribution(tmp_path, monkeypatch, setup_cfg)

    assert {} == dist.cmdclass


def test_a_develop_command_without_an_uninstall_option_is_not_wrapped(tmp_path, monkeypatch):
    class DevelopStub(setuptools.Command):
        user_options = [('editable', 'e', 'install in editable mode')]

    dist = _distribution(
        tmp_path, monkeypatch, '[nodl_generate_py.echo_base]\nx = 1\n', cmdclass={'develop': DevelopStub}
    )

    assert DevelopStub is dist.cmdclass['develop']
    assert issubclass(dist.cmdclass['build_py'], setuptools.command.build_py.build_py)


def test_a_develop_command_with_an_uninstall_option_is_wrapped(tmp_path, monkeypatch):
    class Develop(setuptools.Command):
        user_options = [('uninstall', 'u', 'uninstall')]

    dist = _distribution(tmp_path, monkeypatch, '[nodl_generate_py.echo_base]\nx = 1\n', cmdclass={'develop': Develop})

    assert issubclass(dist.cmdclass['develop'], Develop)
    assert Develop is not dist.cmdclass['develop']
