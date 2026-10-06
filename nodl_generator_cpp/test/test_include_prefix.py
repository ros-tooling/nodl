# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0

"""Tests for the ``--include-prefix`` option."""

import pytest

from nodl_generator_cpp.cli import main
from nodl_generator_cpp.cmake_deps import generated_filenames
from nodl_generator_cpp.generate import cmake_deps, generate_cpp
from nodl_generator_cpp.include_prefix import validate_include_prefix
from nodl_schema import dump_nodl
from nodl_schema.models import NodlDocument, Reference

VALID_PREFIXES = ['my_package', '_private', 'pkg2', '2pkg', 'my-pkg', 'a.b', 'a..b', 'my_package/detail', 'a/b/c']
INVALID_PREFIXES = [
    '',
    '/',
    '/my_package',
    'my_package/',
    'my_package//detail',
    '..',
    '../pkg',
    'pkg/..',
    'a/../b',
    '.',
    './pkg',
    '.hidden',
    '-pkg',
    'pkg\n',
    'a\\b',
    'my pkg',
]


@pytest.fixture()
def root_nodl(fake_resolver, tmp_path):
    path = tmp_path / 'root.nodl.yaml'
    path.write_text(dump_nodl(NodlDocument(include=[Reference(ref='test://rclcpp_node')])))
    return path


@pytest.mark.parametrize('prefix', [None, *VALID_PREFIXES])
def test_valid_prefix(prefix):
    validate_include_prefix(prefix)


@pytest.mark.parametrize('prefix', INVALID_PREFIXES)
def test_invalid_prefix(prefix):
    with pytest.raises(ValueError, match='include_prefix'):
        validate_include_prefix(prefix)


@pytest.mark.parametrize('prefix', INVALID_PREFIXES)
def test_generate_cpp_rejects_invalid_prefix(root_nodl, prefix):
    with pytest.raises(ValueError, match='include_prefix'):
        generate_cpp(root_nodl, 'my_node_base', include_prefix=prefix)


@pytest.mark.parametrize('prefix', INVALID_PREFIXES)
def test_cmake_deps_rejects_invalid_prefix(root_nodl, prefix):
    with pytest.raises(ValueError, match='include_prefix'):
        cmake_deps(root_nodl, 'my_node_base', include_prefix=prefix)


@pytest.mark.parametrize('flag', [[], ['--cmake-deps']])
def test_cli_rejects_invalid_prefix(root_nodl, tmp_path, capsys, flag):
    out = tmp_path / 'out'
    result = main([
        '--nodl-file',
        str(root_nodl),
        '--output-dir',
        str(out),
        '--target-name',
        'my_node_base',
        '--include-prefix',
        '../escape',
        *flag,
    ])

    assert result == 1
    assert 'include_prefix' in capsys.readouterr().err
    assert not out.exists() or not any(out.rglob('*'))


def test_generated_filenames_without_prefix():
    assert generated_filenames('n', has_parameters=True) == [
        'n.hpp',
        'n.cpp',
        'n_parameters.yaml',
        'n_parameters.hpp',
    ]


def test_generated_filenames_with_prefix_scopes_only_headers():
    assert generated_filenames('n', has_parameters=True, include_prefix='pkg/detail') == [
        'pkg/detail/n.hpp',
        'n.cpp',
        'n_parameters.yaml',
        'pkg/detail/n_parameters.hpp',
    ]


def test_generated_filenames_with_prefix_and_no_parameters():
    assert generated_filenames('n', has_parameters=False, include_prefix='pkg') == ['pkg/n.hpp', 'n.cpp']


def test_cmake_deps_lists_prefixed_paths(root_nodl):
    result = cmake_deps(root_nodl, 'my_node_base', include_prefix='my_package')

    assert result.generated_filenames == ['my_package/my_node_base.hpp', 'my_node_base.cpp']
    assert 'my_package/my_node_base.hpp' in result.format('my_node_base')


def test_nested_prefix_layout_and_includes(root_nodl, tmp_path):
    out = tmp_path / 'out'
    result = main([
        '--nodl-file',
        str(root_nodl),
        '--output-dir',
        str(out),
        '--target-name',
        'my_node_base',
        '--include-prefix',
        'my_package/detail',
    ])

    assert result == 0
    assert sorted(f.relative_to(out).as_posix() for f in out.rglob('*') if f.is_file()) == [
        'my_node_base.cpp',
        'my_package/detail/my_node_base.hpp',
    ]
    assert '#include "my_package/detail/my_node_base.hpp"' in (out / 'my_node_base.cpp').read_text()
