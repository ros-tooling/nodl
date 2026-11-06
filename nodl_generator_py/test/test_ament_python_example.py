# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Build, install, test and run the ``echo_robot_py`` package from the ``nodl_generator_py`` documentation.

The documentation includes the package's files, so this checks what it shows.
Each test builds a copy, so nothing is written next to the documentation.
The symlink install tests run ``colcon build --symlink-install``, which needs ``colcon`` and a setuptools older than 80.
"""

import importlib.util
import os
import shutil
import signal
import stat
import subprocess
import sys
import time
from pathlib import Path

import pytest
import rclpy
from marks import needs_colcon, needs_setuptools_lt_80
from rclpy.node import Node
from std_msgs.msg import String

EXAMPLE_DIR = Path(__file__).resolve().parents[1] / 'doc' / 'examples' / 'echo_robot_py'
GENERATED_FILES = {'__init__.py', 'echo_node_base.py', 'echo_node_base_parameters.py'}
STARTUP_TIMEOUT_S = 30.0
EXIT_TIMEOUT_S = 15.0


def _run(command, **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(command, capture_output=True, text=True, check=False, **kwargs)


def _setup(source: Path, *arguments) -> subprocess.CompletedProcess:
    return _run([sys.executable, 'setup.py', *arguments], cwd=source)


def _copy_example(destination: Path) -> Path:
    shutil.copytree(EXAMPLE_DIR, destination)
    return destination


def _generated_files(root: Path) -> set[Path]:
    """Return the generated modules under ``root``, wherever the install layout put the package."""
    return {path for path in root.rglob('echo_robot_py/generated/*.py')}


def _registered_files(root: Path, resource: str = 'echo_node_base') -> set[Path]:
    """Return the ament index entry and the share copy of a registered document under ``root``."""
    return {
        *root.rglob(f'share/ament_index/resource_index/nodl/echo_robot_py__{resource}'),
        *root.rglob(f'share/echo_robot_py/nodl/{resource}.nodl.yaml'),
    }


def _assert_recorded(installed: set[Path], record: Path, strip: Path | None = None):
    recorded = {Path(line) for line in record.read_text().splitlines()}
    assert {Path('/') / path.relative_to(strip or '/') for path in installed} <= recorded


def _assert_installed_and_recorded(root: Path, record: Path, strip: Path | None = None, data_root: Path | None = None):
    installed = _generated_files(root)
    assert GENERATED_FILES == {path.name for path in installed}
    registered = _registered_files(data_root or root)
    assert 2 == len(registered)
    assert 1 == len({path.read_text() for path in registered})
    _assert_recorded({*installed, *registered}, record, strip)


@pytest.fixture(scope='module')
def colcon_install(tmp_path_factory):
    """Install a read-only copy of the example as colcon does, and return its source directory and the install layout."""
    root = tmp_path_factory.mktemp('colcon')
    source = _copy_example(root / 'src')
    (root / 'egg').mkdir()
    layout = {name: root / 'install' / name for name in ('lib', 'scripts', 'data')}
    for path in [*source.rglob('*'), source]:
        path.chmod(path.stat().st_mode & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))
    try:
        result = _setup(
            source,
            'egg_info',
            '--egg-base',
            root / 'egg',
            'build',
            '--build-base',
            root / 'build',
            'install',
            '--install-lib',
            layout['lib'],
            '--install-scripts',
            layout['scripts'],
            '--install-data',
            layout['data'],
            '--single-version-externally-managed',
            '--record',
            root / 'install.log',
        )
        assert 0 == result.returncode, result.stderr
        yield source, layout, root
    finally:
        for path in [source, *source.rglob('*')]:
            path.chmod(path.stat().st_mode | stat.S_IWUSR)


def _colcon_build(source: Path, root: Path) -> subprocess.CompletedProcess:
    return _run([
        'colcon',
        '--log-base',
        root / 'log',
        'build',
        '--base-paths',
        source,
        '--build-base',
        root / 'build',
        '--install-base',
        root / 'install',
        '--symlink-install',
    ])


def _symlink_build(root: Path) -> tuple[Path, dict[str, Path]]:
    """Copy the example for ``colcon build --symlink-install``, and return its source directory and layout.

    The layout is where that build puts the importable package, in the build space, the script, and the data files.
    """
    source = _copy_example(root / 'src')
    # The example is ignored by the colcon build of this repository.
    (source / 'COLCON_IGNORE').unlink()
    layout = {
        'lib': root / 'build' / 'echo_robot_py',
        'scripts': root / 'install' / 'echo_robot_py' / 'lib' / 'echo_robot_py',
        'data': root / 'install' / 'echo_robot_py',
    }
    return source, layout


@pytest.fixture(scope='module')
def colcon_symlink_install(tmp_path_factory):
    """Build a read-only copy of the example with ``colcon build --symlink-install``, and return its source directory and layout."""
    root = tmp_path_factory.mktemp('colcon_symlink')
    source, layout = _symlink_build(root)
    for path in [*source.rglob('*'), source]:
        path.chmod(path.stat().st_mode & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))
    try:
        result = _colcon_build(source, root)
        assert 0 == result.returncode, result.stdout + result.stderr
        yield source, layout
    finally:
        for path in [source, *source.rglob('*')]:
            path.chmod(path.stat().st_mode | stat.S_IWUSR)


@pytest.fixture(
    params=['colcon_install', pytest.param('colcon_symlink_install', marks=[needs_colcon, needs_setuptools_lt_80])]
)
def built(request):
    """The source directory and layout of the example, as installed and as built with ``--symlink-install``."""
    return request.getfixturevalue(request.param)[:2]


def test_colcon_install_installs_and_records_the_generated_modules(colcon_install):
    _, layout, root = colcon_install

    _assert_installed_and_recorded(layout['lib'], root / 'install.log', data_root=layout['data'])


def test_build_then_install_skip_build_installs_and_records_the_generated_modules(tmp_path):
    source = _copy_example(tmp_path / 'src')
    root = tmp_path / 'root'

    assert 0 == _setup(source, 'build').returncode
    result = _setup(source, 'install', '--skip-build', '--root', root, '--record', tmp_path / 'install.log')

    assert 0 == result.returncode, result.stderr
    _assert_installed_and_recorded(root, tmp_path / 'install.log', strip=root)


def test_debian_layout_installs_and_records_the_generated_modules(tmp_path):
    source = _copy_example(tmp_path / 'src')
    root = tmp_path / 'root'
    if 'install-layout' not in _setup(source, 'install', '--help').stdout:
        pytest.skip('this setuptools has no Debian install layout')

    result = _setup(source, 'install', '--install-layout', 'deb', '--root', root, '--record', tmp_path / 'install.log')

    assert 0 == result.returncode, result.stderr
    _assert_installed_and_recorded(root, tmp_path / 'install.log', strip=root)


def test_example_does_not_write_to_the_source_tree(built):
    source, _ = built

    assert not list(source.rglob('generated'))
    assert not list(source.rglob('*_parameters.*'))


def test_rebuild_regenerates_the_modules_of_an_edited_document(tmp_path):
    source = _copy_example(tmp_path / 'src')
    generated = tmp_path / 'build' / 'lib' / 'echo_robot_py' / 'generated'
    assert 0 == _setup(source, 'build', '--build-base', tmp_path / 'build').returncode
    assert (generated / 'echo_node_base_parameters.py').exists()

    document = source / 'nodl' / 'echo_node.nodl.yaml'
    document.write_text(
        document.read_text().replace('parameters:\n  greeting:\n    type: string\n    default_value: hello\n', '')
    )
    result = _setup(source, 'build', '--build-base', tmp_path / 'build')

    assert 0 == result.returncode, result.stderr
    assert (generated / 'echo_node_base.py').exists()
    assert not (generated / 'echo_node_base_parameters.py').exists()


def test_rebuild_drops_the_modules_of_a_removed_document(tmp_path):
    source = _copy_example(tmp_path / 'src')
    setup_py = source / 'setup.py'
    original = setup_py.read_text()
    declaration = "nodl_generate_py('echo_node_base', 'nodl/echo_node.nodl.yaml')"
    setup_py.write_text(
        original.replace(
            declaration, f"{declaration}, nodl_generate_py('other_base', 'nodl/echo_node.nodl.yaml', no_index=True)"
        )
    )
    generated = tmp_path / 'build' / 'lib' / 'echo_robot_py' / 'generated'
    assert 0 == _setup(source, 'build', '--build-base', tmp_path / 'build').returncode
    assert (generated / 'other_base.py').exists()

    setup_py.write_text(original)
    result = _setup(source, 'build', '--build-base', tmp_path / 'build')

    assert 0 == result.returncode, result.stderr
    assert (generated / 'echo_node_base.py').exists()
    assert not (generated / 'other_base.py').exists()


ECHO_DECLARATION = "nodl_generate_py('echo_node_base', 'nodl/echo_node.nodl.yaml')"
STATUS_DECLARATION = "nodl_generate_py('status_base', 'nodl/status.nodl.yaml')"


def _declare(source: Path, *declarations: str) -> None:
    """Replace the declaration of the echo document in the setup.py of a copy of the example."""
    setup_py = source / 'setup.py'
    setup_py.write_text(setup_py.read_text().replace(ECHO_DECLARATION, ', '.join(declarations)))


def _include_status(source: Path) -> None:
    """Make the echo document include the ``status`` document by a ``local://`` reference."""
    (source / 'nodl' / 'status.nodl.yaml').write_text(
        'nodl_version: 2\npublishers:\n  - name: status\n    type: std_msgs/msg/String\n'
        '    qos:\n      history: KEEP_LAST\n      depth: 10\n      reliability: RELIABLE\n'
    )
    document = source / 'nodl' / 'echo_node.nodl.yaml'
    document.write_text(
        document.read_text().replace('parameters:', 'include:\n  - ref: local://status.nodl.yaml\n\nparameters:')
    )


def test_document_with_a_local_include_generates_imports_and_registers_after_install(tmp_path):
    source = _copy_example(tmp_path / 'src')
    root = tmp_path / 'root'
    _include_status(source)
    _declare(source, ECHO_DECLARATION, STATUS_DECLARATION)

    result = _setup(source, 'build', 'install', '--root', root, '--record', tmp_path / 'install.log')

    assert 0 == result.returncode, result.stderr
    (module,) = root.rglob('echo_robot_py/generated/echo_node_base.py')
    assert 'pub_status' in module.read_text()
    lib = module.parents[2]
    imported = _run([sys.executable, '-c', 'import echo_robot_py.echo_node'], env=_with_package({'lib': lib}))
    assert 0 == imported.returncode, imported.stderr
    registered = _registered_files(root)
    assert 2 == len(registered)
    for path in registered:
        assert 'ref: nodl://echo_robot_py/status_base' in path.read_text()
        assert 'local://' not in path.read_text()
    _assert_recorded({*registered, *_registered_files(root, 'status_base')}, tmp_path / 'install.log', strip=root)


def test_unregistered_local_include_fails_the_install(tmp_path):
    source = _copy_example(tmp_path / 'src')
    _include_status(source)
    _declare(source, ECHO_DECLARATION, "nodl_generate_py('status_base', 'nodl/status.nodl.yaml', no_index=True)")

    result = _setup(source, 'install', '--root', tmp_path / 'root')

    assert 0 != result.returncode
    error = ' '.join(result.stderr.split())
    assert (
        'error: nodl_generator_py: echo_robot_py__echo_node_base includes a local:// reference that is not registered'
        in error
    )
    assert 'Register the included file with nodl_generate_py() in the same package' in error
    assert 'Traceback' not in result.stderr


def test_resource_name_registers_the_document_under_that_name(tmp_path):
    source = _copy_example(tmp_path / 'src')
    _declare(source, "nodl_generate_py('echo_node_base', 'nodl/echo_node.nodl.yaml', resource_name='echo')")
    root = tmp_path / 'root'

    result = _setup(source, 'install', '--root', root)

    assert 0 == result.returncode, result.stderr
    assert 2 == len(_registered_files(root, 'echo'))
    assert not _registered_files(root, 'echo_node_base')
    assert GENERATED_FILES == {path.name for path in _generated_files(root)}


def test_no_index_installs_the_modules_without_registering_the_document(tmp_path):
    source = _copy_example(tmp_path / 'src')
    _declare(source, "nodl_generate_py('echo_node_base', 'nodl/echo_node.nodl.yaml', no_index=True)")
    root = tmp_path / 'root'

    result = _setup(source, 'install', '--root', root)

    assert 0 == result.returncode, result.stderr
    assert not _registered_files(root)
    assert not list(root.rglob('nodl'))
    assert GENERATED_FILES == {path.name for path in _generated_files(root)}


def test_registering_without_data_files_fails_the_build(tmp_path):
    source = _copy_example(tmp_path / 'src')
    setup_py = source / 'setup.py'
    text = setup_py.read_text()
    start, end = text.index('    data_files=['), text.index('    entry_points')
    setup_py.write_text(text[:start] + text[end:])

    result = _setup(source, 'build', '--build-base', tmp_path / 'build')

    assert 0 != result.returncode
    assert 'error: nodl_generator_py: registering documents needs setup() to list data_files' in result.stderr
    assert 'Traceback' not in result.stderr


def test_file_registered_under_two_names_fails(tmp_path):
    source = _copy_example(tmp_path / 'src')
    _declare(source, ECHO_DECLARATION, "nodl_generate_py('other_base', 'nodl/echo_node.nodl.yaml')")

    result = _setup(source, 'build', '--build-base', tmp_path / 'build')

    assert 0 != result.returncode
    assert "nodl_generator_py: targets 'echo_node_base' and 'other_base' both register" in result.stderr


def test_invalid_document_fails_the_build_naming_its_file(tmp_path):
    source = _copy_example(tmp_path / 'src')
    (source / 'nodl' / 'echo_node.nodl.yaml').write_text('nodl_version: 2\npublishers: not-a-list\n')

    result = _setup(source, 'build', '--build-base', tmp_path / 'build')

    assert 0 != result.returncode
    assert 'error: nodl_generator_py: nodl/echo_node.nodl.yaml:' in result.stderr
    assert 'Traceback' not in result.stderr


def _develop_target(tmp_path: Path) -> tuple[Path, dict[str, str]]:
    target = tmp_path / 'develop'
    target.mkdir()
    environment = {
        **os.environ,
        'PYTHONPATH': os.pathsep.join(filter(None, [str(target), os.environ.get('PYTHONPATH')])),
    }
    return target, environment


@needs_setuptools_lt_80
def test_develop_outside_a_symlink_build_space_fails_with_a_clear_error(tmp_path):
    source = _copy_example(tmp_path / 'src')
    target, environment = _develop_target(tmp_path)

    result = _run(
        [sys.executable, 'setup.py', 'develop', '--install-dir', target, '--script-dir', target],
        cwd=source,
        env=environment,
    )

    assert 0 != result.returncode
    assert 'error: nodl_generator_py: setup.py develop needs to run in the build space of colcon build' in result.stderr
    assert not list(source.rglob('generated'))


@needs_setuptools_lt_80
def test_develop_uninstall_generates_nothing(tmp_path):
    source = _copy_example(tmp_path / 'src')
    target, environment = _develop_target(tmp_path)

    result = _run(
        [sys.executable, 'setup.py', 'develop', '--uninstall', '--install-dir', target, '--script-dir', target],
        cwd=source,
        env=environment,
    )

    assert 0 == result.returncode, result.stderr
    assert not list(source.rglob('generated'))


@needs_setuptools_lt_80
def test_develop_in_the_source_tree_keeps_a_symlinked_package(tmp_path):
    source = _copy_example(tmp_path / 'src')
    package = source / 'echo_robot_py'
    elsewhere = tmp_path / 'elsewhere'
    package.rename(elsewhere)
    package.symlink_to(elsewhere)
    target, environment = _develop_target(tmp_path)

    result = _run(
        [sys.executable, 'setup.py', 'develop', '--install-dir', target, '--script-dir', target],
        cwd=source,
        env=environment,
    )

    assert 0 != result.returncode
    assert 'develop needs to run in the build space of colcon build' in result.stderr
    assert package.is_symlink()
    assert not list(elsewhere.rglob('generated'))


@needs_setuptools_lt_80
def test_develop_twice_in_a_build_space_keeps_the_generated_modules_importable(tmp_path):
    source = _copy_example(tmp_path / 'src')
    space = tmp_path / 'space'
    space.mkdir()
    for name in ('setup.py', 'setup.cfg', 'package.xml', 'echo_robot_py'):
        (space / name).symlink_to(source / name)
    target, environment = _develop_target(tmp_path)
    command = [
        *('setup.py', 'develop', '--editable', '--build-directory', space / 'build', '--no-deps'),
        *('--install-dir', target, '--script-dir', target),
    ]

    for _ in range(2):
        result = _run([sys.executable, *command], cwd=space, env=environment)
        assert 0 == result.returncode, result.stderr
    imported = _run(
        [sys.executable, '-c', 'import echo_robot_py.generated.echo_node_base_parameters'],
        cwd=space,
        env=_with_package({'lib': space}),
    )

    assert 0 == imported.returncode, imported.stderr
    assert not list(source.rglob('generated'))


@pytest.mark.skipif(importlib.util.find_spec('setuptools.command.editable_wheel') is None, reason='no editable_wheel')
def test_editable_wheel_fails_with_a_clear_error(tmp_path):
    source = _copy_example(tmp_path / 'src')

    result = _setup(source, 'editable_wheel', '--dist-dir', tmp_path / 'dist')

    assert 0 != result.returncode
    assert 'error: nodl_generator_py: editable installs with pip are not supported' in result.stderr
    assert not list(source.rglob('generated'))


def test_package_build_py_still_runs(tmp_path):
    source = _copy_example(tmp_path / 'src')
    root = tmp_path / 'root'
    setup_py = source / 'setup.py'
    text = setup_py.read_text()
    text = text.replace(
        'from setuptools import find_packages, setup\n',
        'from setuptools import find_packages, setup\n'
        'from setuptools.command.build_py import build_py\n\n\n'
        'class MyBuildPy(build_py):\n'
        '    def run(self):\n'
        "        Path('my_build_py_ran').touch()\n"
        '        super().run()\n\n',
    )
    text = text.replace(
        "'nodl/echo_node.nodl.yaml'))", "'nodl/echo_node.nodl.yaml'), cmdclass={'build_py': MyBuildPy})"
    )
    setup_py.write_text(text)

    result = _setup(source, 'build', 'install', '--root', root, '--record', tmp_path / 'install.log')

    assert 0 == result.returncode, result.stderr
    assert (source / 'my_build_py_ran').exists()
    _assert_installed_and_recorded(root, tmp_path / 'install.log', strip=root)


@needs_colcon
@needs_setuptools_lt_80
def test_symlink_install_imports_the_generated_modules_from_the_build_space(colcon_symlink_install):
    _, layout = colcon_symlink_install

    result = _run(
        [sys.executable, '-c', 'import echo_robot_py.generated.echo_node_base_parameters'], env=_with_package(layout)
    )

    assert 0 == result.returncode, result.stderr


@needs_colcon
@needs_setuptools_lt_80
def test_symlink_install_registers_the_documents_from_the_build_space(colcon_symlink_install):
    source, layout = colcon_symlink_install

    registered = _registered_files(layout['data'])

    assert 2 == len(registered)
    assert 1 == len({path.read_text() for path in registered})
    assert all(source not in path.resolve().parents for path in registered)


# The package_dir of setup.py, where the package moves to, and the build space directory that holds the built package.
PACKAGE_LAYOUTS = {
    'src': ("package_dir={'': 'src'}, packages=find_packages('src')", 'src/echo_robot_py', 'src'),
    'renamed': ("package_dir={'echo_robot_py': 'pkgdir'}, packages=['echo_robot_py']", 'pkgdir', '.'),
}


@needs_colcon
@needs_setuptools_lt_80
@pytest.mark.parametrize('name', PACKAGE_LAYOUTS)
def test_symlink_install_imports_the_generated_modules_from_a_package_in_another_directory(tmp_path, name):
    package_dir, moved_to, built_in = PACKAGE_LAYOUTS[name]
    source, layout = _symlink_build(tmp_path)
    setup_py = source / 'setup.py'
    setup_py.write_text(setup_py.read_text().replace("packages=find_packages(exclude=['test', 'test.*'])", package_dir))
    (source / moved_to).parent.mkdir(exist_ok=True)
    (source / 'echo_robot_py').rename(source / moved_to)

    # A second build runs develop in a build space that has the overlay of the first.
    for _ in range(2):
        result = _colcon_build(source, tmp_path)
        assert 0 == result.returncode, result.stdout + result.stderr
    imported = _run(
        [sys.executable, '-c', 'import echo_robot_py.generated.echo_node_base_parameters'],
        env=_with_package({'lib': layout['lib'] / built_in}),
    )

    assert 0 == imported.returncode, imported.stderr


@needs_colcon
@needs_setuptools_lt_80
def test_symlink_install_takes_edits_to_a_package_module_and_regenerates_an_edited_document(tmp_path):
    source, layout = _symlink_build(tmp_path)
    _include_status(source)
    _declare(source, ECHO_DECLARATION, STATUS_DECLARATION)
    assert 0 == _colcon_build(source, tmp_path).returncode
    generated = layout['lib'] / 'echo_robot_py' / 'generated'
    assert (generated / 'echo_node_base_parameters.py').exists()
    registered = _registered_files(layout['data'])
    assert 2 == len(registered)
    for path in registered:
        assert 'ref: nodl://echo_robot_py/status_base' in path.read_text()
        assert source not in path.resolve().parents

    with (source / 'echo_robot_py' / 'echo_node.py').open('a') as module:
        module.write('\nEDITED = True\n')
    imported = _run(
        [sys.executable, '-c', 'import echo_robot_py.echo_node as m; assert m.EDITED'], env=_with_package(layout)
    )
    assert 0 == imported.returncode, imported.stderr

    document = source / 'nodl' / 'echo_node.nodl.yaml'
    document.write_text(
        document.read_text().replace('parameters:\n  greeting:\n    type: string\n    default_value: hello\n', '')
    )
    result = _colcon_build(source, tmp_path)

    assert 0 == result.returncode, result.stdout + result.stderr
    assert (generated / 'echo_node_base.py').exists()
    assert not (generated / 'echo_node_base_parameters.py').exists()


def _with_package(layout) -> dict[str, str]:
    return {
        **os.environ,
        'PYTHONPATH': os.pathsep.join(filter(None, [str(layout['lib']), os.environ.get('PYTHONPATH')])),
    }


def test_example_tests_pass_against_the_installed_package(built):
    source, layout = built

    result = _run([sys.executable, '-m', 'pytest', '-p', 'no:cacheprovider'], cwd=source, env=_with_package(layout))

    assert 0 == result.returncode, result.stdout


@pytest.fixture
def harness(monkeypatch):
    # Other packages' tests run at the same time, and some use the same topic names.
    monkeypatch.setenv('ROS_DOMAIN_ID', str(os.getpid() % 100 + 100))
    rclpy.init()
    node = Node('echo_robot_py_harness')
    try:
        yield node
    finally:
        node.destroy_node()
        rclpy.shutdown()


def test_installed_executable_echoes_with_the_declared_parameter(built, harness):
    _, layout = built
    received = []
    harness.create_subscription(String, 'echo_out', lambda msg: received.append(msg.data), 10)
    publisher = harness.create_publisher(String, 'echo_in', 10)

    process = subprocess.Popen([layout['scripts'] / 'echo_node'], env=_with_package(layout))
    try:
        deadline = time.monotonic() + STARTUP_TIMEOUT_S
        while not received:
            assert process.poll() is None, f'echo_node exited with {process.returncode}'
            assert time.monotonic() < deadline, 'no echo received'
            publisher.publish(String(data='hi'))
            rclpy.spin_once(harness, timeout_sec=0.2)

        assert 'hello: hi' == received[0]

        process.send_signal(signal.SIGINT)
        assert 0 == process.wait(timeout=EXIT_TIMEOUT_S)
    finally:
        if process.poll() is None:
            process.kill()
        process.wait()
