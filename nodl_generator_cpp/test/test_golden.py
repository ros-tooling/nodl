# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0

"""Golden-file tests for nodl_generator_cpp.

Each subdirectory under ``golden/`` (except ``includes/``) is a test case:
  - ``input.nodl.yaml`` — the root NoDL document
  - ``expected/``       — the files the generator should produce

Files in ``expected/`` are byte-compared against the generated output,
with two exceptions:
  - ``*_deps.cmake`` — compared separately (with path normalization) by
    :func:`test_golden_cmake_deps`.
  - ``<name>.exists`` — an *existence-only marker*: it documents that
    ``<name>`` must be generated, but its contents are intentionally not
    asserted. Use this for output owned by an external, version-varying
    tool (e.g. ``generate_parameter_library``'s ``*_parameters.hpp``),
    where the exact text depends on the installed dependency version.
    The marker file's own contents are ignored (they can hold a note
    explaining why the file is existence-only).

Include references use ``test://`` URIs resolved by the shared
FakeResolver fixture (see conftest.py), which loads every file from
``_includes/`` so that base-class and library nodl files are
written once and shared across all cases.
"""

import re
from pathlib import Path

import pytest

from nodl_generator_cpp.cli import main

GOLDEN_DIR = Path(__file__).parent / 'golden'

# Discover test cases: every subdirectory with an input.nodl.yaml
_CASES = sorted(d.name for d in GOLDEN_DIR.iterdir() if d.is_dir() and (d / 'input.nodl.yaml').exists())


_CMAKE_DEPS_SUFFIX = '_deps.cmake'
_EXISTS_MARKER_SUFFIX = '.exists'


def _normalize_cmake_deps(text: str) -> str:
    """Replace absolute path prefixes with ``/RESOLVED/`` so golden files are portable."""
    return re.sub(r'(?<=  )/\S+/([^\s/]+)', r'/RESOLVED/\1', text)


@pytest.mark.parametrize('case', _CASES)
def test_golden(fake_resolver, tmp_path, case):
    case_dir = GOLDEN_DIR / case
    input_file = case_dir / 'input.nodl.yaml'
    expected_dir = case_dir / 'expected'

    result = main([
        '--nodl-file',
        str(input_file),
        '--output-dir',
        str(tmp_path),
        '--target-name',
        'my_node_base',
    ])

    assert result == 0, 'CLI returned non-zero'

    # Entries to consider (*_deps.cmake is compared by test_golden_cmake_deps).
    entries = sorted(f for f in expected_dir.iterdir() if not f.name.endswith(_CMAKE_DEPS_SUFFIX))
    assert entries, f'No expected files in {expected_dir}'

    # ``<name>.exists`` markers: the file must be generated, but its
    # contents are not asserted (external, version-varying output).
    existence_only = {f.name[: -len(_EXISTS_MARKER_SUFFIX)] for f in entries if f.name.endswith(_EXISTS_MARKER_SUFFIX)}
    content_files = [f for f in entries if not f.name.endswith(_EXISTS_MARKER_SUFFIX)]

    # Existence-only files must be generated; contents are intentionally not checked.
    for name in sorted(existence_only):
        assert (tmp_path / name).exists(), f'{name} was not generated'

    # Every remaining expected file must be generated with identical content.
    for expected_file in content_files:
        generated = tmp_path / expected_file.name
        assert generated.exists(), f'{expected_file.name} was not generated'

        expected_text = expected_file.read_text()
        generated_text = generated.read_text()
        assert generated_text == expected_text, (
            f'{expected_file.name} does not match golden file.\n'
            f'--- expected ({expected_file})\n'
            f'+++ generated ({generated})\n'
        )

    # No unexpected files.
    generated_names = {f.name for f in tmp_path.iterdir()}
    expected_names = {f.name for f in content_files} | existence_only
    extra = generated_names - expected_names
    assert not extra, f'Unexpected generated files: {extra}'


@pytest.mark.parametrize('case', _CASES)
def test_golden_cmake_deps(fake_resolver, tmp_path, case):
    case_dir = GOLDEN_DIR / case
    input_file = case_dir / 'input.nodl.yaml'
    expected_dir = case_dir / 'expected'

    result = main([
        '--nodl-file',
        str(input_file),
        '--output-dir',
        str(tmp_path),
        '--target-name',
        'my_node_base',
        '--cmake-deps',
    ])

    assert result == 0, 'CLI --cmake-deps returned non-zero'

    # Exactly one file should be produced.
    generated_files = list(tmp_path.iterdir())
    assert len(generated_files) == 1, f'Expected 1 file, got {[f.name for f in generated_files]}'

    generated_file = generated_files[0]
    assert generated_file.name == 'my_node_base_deps.cmake'

    expected_file = expected_dir / 'my_node_base_deps.cmake'
    assert expected_file.exists(), f'Missing golden file {expected_file}'

    generated_text = _normalize_cmake_deps(generated_file.read_text())
    expected_text = expected_file.read_text()
    assert generated_text == expected_text, (
        f'my_node_base_deps.cmake does not match golden file.\n'
        f'--- expected ({expected_file})\n'
        f'+++ generated ({generated_file})\n'
    )
