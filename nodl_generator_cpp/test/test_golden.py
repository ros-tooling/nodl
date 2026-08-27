# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0

"""Golden-file tests for nodl_generator_cpp.

Each subdirectory under ``golden/`` (except ``includes/``) is a test case:
  - ``input.nodl.yaml`` — the root NoDL document
  - ``expected/``       — the files the generator should produce

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
        'my_node',
    ])

    assert result == 0, 'CLI returned non-zero'

    # Every expected file (excluding *_deps.cmake) must be generated with identical content.
    expected_files = sorted(f for f in expected_dir.iterdir() if not f.name.endswith(_CMAKE_DEPS_SUFFIX))
    assert expected_files, f'No expected files in {expected_dir}'

    for expected_file in expected_files:
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
    expected_names = {f.name for f in expected_files}
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
        'my_node',
        '--cmake-deps',
    ])

    assert result == 0, 'CLI --cmake-deps returned non-zero'

    # Exactly one file should be produced.
    generated_files = list(tmp_path.iterdir())
    assert len(generated_files) == 1, f'Expected 1 file, got {[f.name for f in generated_files]}'

    generated_file = generated_files[0]
    assert generated_file.name == 'my_node_deps.cmake'

    expected_file = expected_dir / 'my_node_deps.cmake'
    assert expected_file.exists(), f'Missing golden file {expected_file}'

    generated_text = _normalize_cmake_deps(generated_file.read_text())
    expected_text = expected_file.read_text()
    assert generated_text == expected_text, (
        f'my_node_deps.cmake does not match golden file.\n'
        f'--- expected ({expected_file})\n'
        f'+++ generated ({generated_file})\n'
    )
