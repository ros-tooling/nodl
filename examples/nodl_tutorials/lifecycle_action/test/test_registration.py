# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Verify the one public contract and both generated lifecycle bases."""

from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from ament_index_python.resources import get_resource, get_resources
from nodl_tutorial_lifecycle_action.generated.fibonacci_action_server_py_base import (
    FibonacciActionServerPyBase,
)
from rclpy.lifecycle import LifecycleNode

PACKAGE = 'nodl_tutorial_lifecycle_action'
EXPECTED = Path(__file__).parent / 'expected'


def test_only_public_contract_is_registered():
    resources = get_resources('nodl')

    assert f'{PACKAGE}__fibonacci' in resources
    assert f'{PACKAGE}__fibonacci_codegen' not in resources


def test_registered_contract_matches_installed_source():
    content, prefix = get_resource('nodl', f'{PACKAGE}__fibonacci')

    assert prefix
    installed = Path(get_package_share_directory(PACKAGE)) / 'nodl' / 'fibonacci.nodl.yaml'
    assert installed.read_text() == content


def test_python_base_uses_lifecycle_provider():
    assert issubclass(FibonacciActionServerPyBase, LifecycleNode)
    assert hasattr(FibonacciActionServerPyBase, 'execute_fibonacci')


def test_documented_generated_bases_match_build():
    generated = Path.cwd() / 'nodl_generated'
    cpp = generated / 'fibonacci_action_server_cpp_base'
    actual_cpp = (
        '// fibonacci_action_server_cpp_base.hpp\n'
        + (cpp / 'fibonacci_action_server_cpp_base.hpp').read_text()
        + '\n// fibonacci_action_server_cpp_base.cpp\n'
        + (cpp / 'fibonacci_action_server_cpp_base.cpp').read_text()
    )
    python = (
        generated / 'fibonacci_action_server_py_base' / PACKAGE / 'generated' / 'fibonacci_action_server_py_base.py'
    )

    assert actual_cpp.strip() == (EXPECTED / 'generated_cpp.txt').read_text().strip()
    assert python.read_text().strip() == (EXPECTED / 'generated_python.txt').read_text().strip()
