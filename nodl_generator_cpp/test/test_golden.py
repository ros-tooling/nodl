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

from pathlib import Path

import pytest

from nodl_generator_cpp.cli import main

GOLDEN_DIR = Path(__file__).parent / 'golden'

# Discover test cases: every subdirectory with an input.nodl.yaml
_CASES = sorted(d.name for d in GOLDEN_DIR.iterdir() if d.is_dir() and (d / 'input.nodl.yaml').exists())


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

    # Every expected file must be generated with identical content.
    expected_files = sorted(expected_dir.iterdir())
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
