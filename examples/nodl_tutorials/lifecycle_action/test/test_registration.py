# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Verify each independent package's contract and generated lifecycle base."""

import importlib
from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from ament_index_python.resources import get_resource, get_resources
from rclpy.lifecycle import LifecycleNode

PACKAGE = Path.cwd().name
LANGUAGE = PACKAGE.removeprefix('nodl_tutorial_lifecycle_action_')
EXPECTED = Path(__file__).parent / 'expected'
TARGET = f'fibonacci_action_server_{LANGUAGE}_base'
GENERATED = Path.cwd() / 'nodl_generated' / TARGET


def test_only_public_contract_is_registered():
    resources = get_resources('nodl')

    assert {name for name in resources if name.startswith(f'{PACKAGE}__')} == {f'{PACKAGE}__fibonacci'}


def test_registered_contract_matches_installed_source():
    content, prefix = get_resource('nodl', f'{PACKAGE}__fibonacci')

    assert prefix
    installed = Path(get_package_share_directory(PACKAGE)) / 'nodl' / 'fibonacci.nodl.yaml'
    assert installed.read_text() == content


def test_base_uses_lifecycle_provider():
    if LANGUAGE == 'cpp':
        header = (GENERATED / PACKAGE / f'{TARGET}.hpp').read_text()
        assert 'public rclcpp_lifecycle::LifecycleNode' in header
    else:
        module = importlib.import_module(f'{PACKAGE}.generated.{TARGET}')
        assert issubclass(module.FibonacciActionServerPyBase, LifecycleNode)
        assert hasattr(module.FibonacciActionServerPyBase, 'execute_fibonacci')


def test_documented_generated_base_matches_build():
    if LANGUAGE == 'cpp':
        actual = (
            f'// {TARGET}.hpp\n'
            + (GENERATED / PACKAGE / f'{TARGET}.hpp').read_text()
            + f'\n// {TARGET}.cpp\n'
            + (GENERATED / f'{TARGET}.cpp').read_text()
        )
        expected = EXPECTED / 'generated_cpp.txt'
    else:
        actual = (GENERATED / PACKAGE / 'generated' / f'{TARGET}.py').read_text()
        expected = EXPECTED / 'generated_python.txt'
    assert actual.strip() == expected.read_text().strip()
