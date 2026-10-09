# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0

"""Argument-validation tests for the ``nodl_generate_cpp`` CMake macro.

Each case runs the macro from a ``cmake -P`` script.
Validation happens before any target or process is created, so script mode reaches it.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

MACRO_FILE = Path(__file__).parent.parent / 'cmake' / 'nodl_generate_cpp.cmake'

pytestmark = pytest.mark.skipif(shutil.which('cmake') is None, reason='cmake not on PATH')


def _run_macro(tmp_path: Path, call_args: str, *, in_function: bool = False) -> subprocess.CompletedProcess:
    call = f'nodl_generate_cpp({call_args})'
    if in_function:
        call = f'function(wrapper)\n  {call}\nendfunction()\nwrapper()'
    script = tmp_path / 'call.cmake'
    script.write_text(f'include("{MACRO_FILE.as_posix()}")\n{call}\n')
    return subprocess.run(
        ['cmake', '-P', str(script)],
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.parametrize(
    ('call_args', 'expected'),
    [
        ('my_base SHARED STATIC my.nodl.yaml', "target 'my_base' cannot be both SHARED and STATIC"),
        ('my_base', "target 'my_base' requires exactly one NODL_FILE, got 0"),
        ('my_base STATIC', "target 'my_base' requires exactly one NODL_FILE, got 0"),
        ('my_base EXPORT', "target 'my_base' requires exactly one NODL_FILE, got 0"),
        ('my_base NO_INDEX', "target 'my_base' requires exactly one NODL_FILE, got 0"),
        ('my_base a.nodl.yaml b.nodl.yaml', "target 'my_base' requires exactly one NODL_FILE, got 2"),
        ('my_base my.nodl.yaml RESOURCE_NAME', "target 'my_base' has a RESOURCE_NAME with no value"),
        ('my_base RESOURCE_NAME "" my.nodl.yaml', "target 'my_base' requires exactly one NODL_FILE, got 0"),
    ],
    ids=[
        'shared-and-static',
        'missing-file',
        'missing-file-with-type',
        'missing-file-with-export',
        'missing-file-with-no-index',
        'two-files',
        'resource-name-without-value',
        'empty-resource-name-consumes-the-file',
    ],
)
def test_bad_arguments_are_rejected(tmp_path, call_args, expected):
    result = _run_macro(tmp_path, call_args)

    assert result.returncode != 0
    assert 'nodl_generate_cpp:' in result.stderr
    assert expected in result.stderr


@pytest.mark.parametrize(
    ('call_args', 'rejected'),
    [
        ('my_base my.nodl.yaml', False),
        ('my_base SHARED my.nodl.yaml', False),
        ('my_base EXPORT my.nodl.yaml', True),
        ('my_base SHARED EXPORT my.nodl.yaml', True),
        ('my_base STATIC my.nodl.yaml', False),
        ('my_base STATIC EXPORT my.nodl.yaml', True),
    ],
    ids=['default', 'shared', 'export', 'shared-export', 'static', 'static-export'],
)
def test_exported_target_is_rejected_inside_a_function(tmp_path, call_args, rejected):
    result = _run_macro(tmp_path, call_args, in_function=True)

    stderr = ' '.join(result.stderr.split())
    assert ("cannot be created inside function 'wrapper'" in stderr) is rejected
    if rejected:
        assert 'Turn the function into a macro' in stderr
        assert 'NO_EXPORT' not in stderr


def _configure_project_with_subdirectory(tmp_path: Path, call_args: str) -> subprocess.CompletedProcess:
    """Configure a project that calls the macro from a subdirectory.

    Script mode has no ``add_subdirectory``, so this runs a real configure.
    The configure fails later for lack of a NoDL file, which these tests ignore.
    """
    (tmp_path / 'sub').mkdir()
    (tmp_path / 'sub' / 'CMakeLists.txt').write_text(f'nodl_generate_cpp({call_args})\n')
    (tmp_path / 'CMakeLists.txt').write_text(
        'cmake_minimum_required(VERSION 3.22)\n'
        'project(subdirectory_test NONE)\n'
        f'include("{MACRO_FILE.as_posix()}")\n'
        'add_subdirectory(sub)\n'
    )
    return subprocess.run(
        ['cmake', '-S', str(tmp_path), '-B', str(tmp_path / 'build')],
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.parametrize(
    ('call_args', 'rejected'),
    [
        ('my_base my.nodl.yaml', False),
        ('my_base SHARED my.nodl.yaml', False),
        ('my_base EXPORT my.nodl.yaml', True),
        ('my_base SHARED EXPORT my.nodl.yaml', True),
        ('my_base STATIC my.nodl.yaml', False),
        ('my_base STATIC EXPORT my.nodl.yaml', True),
    ],
    ids=['default', 'shared', 'export', 'shared-export', 'static', 'static-export'],
)
def test_exported_target_is_rejected_in_a_subdirectory(tmp_path, call_args, rejected):
    result = _configure_project_with_subdirectory(tmp_path, call_args)

    stderr = ' '.join(result.stderr.split())
    assert ('cannot be created in subdirectory' in stderr) is rejected
    if rejected:
        assert 'that calls ament_package()' in stderr


def test_exported_target_is_accepted_in_the_project_directory(tmp_path):
    (tmp_path / 'CMakeLists.txt').write_text(
        'cmake_minimum_required(VERSION 3.22)\n'
        'project(toplevel_test NONE)\n'
        f'include("{MACRO_FILE.as_posix()}")\n'
        'nodl_generate_cpp(my_base EXPORT my.nodl.yaml)\n'
    )

    result = subprocess.run(
        ['cmake', '-S', str(tmp_path), '-B', str(tmp_path / 'build')],
        capture_output=True,
        text=True,
        check=False,
    )

    assert 'cannot be created in' not in ' '.join(result.stderr.split())


@pytest.mark.parametrize(
    ('call_args', 'name'),
    [
        ('my_base NO_INDEX RESOURCE_NAME my_node my.nodl.yaml', 'my_node'),
        ('my_base STATIC NO_INDEX RESOURCE_NAME my_node my.nodl.yaml', 'my_node'),
        ('my_base NO_INDEX RESOURCE_NAME off my.nodl.yaml', 'off'),
        ('my_base NO_INDEX RESOURCE_NAME 0 my.nodl.yaml', '0'),
    ],
    ids=['default', 'static', 'falsy-name-off', 'falsy-name-zero'],
)
def test_resource_name_with_no_index_is_rejected(tmp_path, call_args, name):
    result = _run_macro(tmp_path, call_args)

    stderr = ' '.join(result.stderr.split())
    assert result.returncode != 0
    assert f"RESOURCE_NAME '{name}' has no effect" in stderr


@pytest.mark.parametrize(
    'call_args',
    [
        'my_base my.nodl.yaml',
        'my_base SHARED my.nodl.yaml',
        'my_base STATIC my.nodl.yaml',
        'my_base EXPORT my.nodl.yaml',
        'my_base RESOURCE_NAME my_node my.nodl.yaml',
        'my_base RESOURCE_NAME off my.nodl.yaml',
        'my_base RESOURCE_NAME 0 my.nodl.yaml',
        'my_base NO_INDEX my.nodl.yaml',
        'my_base STATIC RESOURCE_NAME my_node my.nodl.yaml',
        'my_base STATIC NO_INDEX my.nodl.yaml',
        'my_base EXPORT RESOURCE_NAME my_node my.nodl.yaml',
        'my_base STATIC EXPORT NO_INDEX my.nodl.yaml',
        'my_base my.nodl.yaml RESOURCE_NAME my_node',
    ],
    ids=[
        'default-name',
        'shared-default-name',
        'static-default-name',
        'export-default-name',
        'resource-name',
        'resource-name-off',
        'resource-name-zero',
        'no-index',
        'static-resource-name',
        'static-no-index',
        'export-resource-name',
        'static-export-no-index',
        'file-first',
    ],
)
def test_valid_index_arguments_pass_validation(tmp_path, call_args):
    result = _run_macro(tmp_path, call_args)

    # The macro goes on to run the generator, which fails for lack of a NoDL file.
    assert 'has no effect' not in result.stderr
    assert '--cmake-deps failed' in result.stderr
