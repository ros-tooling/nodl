# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Launch tests that check a running node against its NoDL document.

``nodl_add_conformance_test`` generates its test from :func:`conformance_test`.
Packages that cannot call CMake, such as ``ament_python`` packages, call it from a test module.
"""

from __future__ import annotations

import os
import re
import sys
import unittest
from collections.abc import Callable, Iterable
from pathlib import Path

import pytest
from launch import LaunchDescription
from launch_ros.actions import Node
from launch_testing.actions import ReadyToTest

from nodl_schema import IgnoreRule
from nodl_schema.composition import resolve, resolver_for
from ros2nodl.conformance import assert_conforms, ignore_from_environment

_NODE_NAME = re.compile(r'[A-Za-z_][A-Za-z0-9_]*')


def _strings(argument: str, values: Iterable[str]) -> list[str]:
    if isinstance(values, str):
        raise TypeError(f'{argument} must be a list of strings, not one string: {values!r}')
    return [str(value) for value in values]


def _existing_file(argument: str, path: str | os.PathLike[str]) -> str:
    if not Path(path).is_absolute():
        raise ValueError(f'{argument} must be absolute, so build it from Path(__file__).parent: {str(path)!r}')
    if not Path(path).is_file():
        raise FileNotFoundError(f'{argument} does not exist: {str(path)!r}')
    return str(path)


def _document(nodl: str | os.PathLike[str]) -> str:
    """Return the path of the document that ``nodl`` names, resolving a reference with the registered NoDL resolvers."""
    if isinstance(nodl, str) and resolver_for(nodl) is not None:
        return str(resolve(nodl))
    return _existing_file('nodl', nodl)


def _parameter(item: str) -> str:
    name, separator, value = item.partition(':=')
    if not (name and separator and value):
        raise ValueError(f'parameters item must be name:=value: {item!r}')
    return item


def _node_fqn(namespace: str, name: str) -> str:
    stripped = namespace.strip('/')
    return f'/{stripped}/{name}' if stripped else f'/{name}'


def conformance_test(
    *,
    package: str,
    executable: str,
    nodl: str | os.PathLike[str],
    node_name: str | None = None,
    node_namespace: str = '/',
    timeout: int = 15,
    parameters: Iterable[str] = (),
    parameters_files: Iterable[str | os.PathLike[str]] = (),
    ignore: Iterable[str] = (),
) -> tuple[Callable[[], LaunchDescription], type[unittest.TestCase]]:
    """Return the launch description and test case that check one executable against one NoDL document.

    Assign the result at module level in a test file:

    .. code-block:: python

        generate_test_description, TestNodlConformance = conformance_test(...)

    Both names are what ``launch_testing`` looks for in a test module.
    ``generate_test_description`` is marked ``launch_test`` so that pytest launches the executable before it runs the test case.
    The test case waits for the node, describes it, and fails with every difference from the document.
    Both belong to the calling module, so reports name that module.
    Rules in the ``NODL_CONFORMANCE_IGNORE`` environment variable apply when the test runs, after ``ignore``.

    The arguments match the options of the ``nodl_add_conformance_test`` CMake macro, and are checked when this function is called.
    See the ``ament_nodl`` overview for each argument.

    :raises ValueError: if an argument is invalid.
    :raises TypeError: if a list argument is a single string.
    :raises FileNotFoundError: if the document or a parameters file does not exist.
    :raises nodl_schema.composition.ResolutionError: if a ``nodl://`` reference does not resolve.
    """
    document = _document(nodl)

    if node_name is None:
        if not _NODE_NAME.fullmatch(executable):
            raise ValueError(f'executable {executable!r} is not a valid node name, pass node_name')
        node_name = executable
    if isinstance(timeout, bool) or not isinstance(timeout, int) or timeout < 1:
        raise ValueError(f'timeout must be a positive integer: {timeout!r}')

    files = [_existing_file('parameters_files item', file) for file in _strings('parameters_files', parameters_files)]
    items = [_parameter(item) for item in _strings('parameters', parameters)]
    rules = [IgnoreRule.parse(rule) for rule in _strings('ignore', ignore)]
    node_namespace = node_namespace or '/'
    ros_arguments = [
        *(argument for file in files for argument in ('--params-file', file)),
        *(argument for item in items for argument in ('-p', item)),
    ]
    node_fqn = _node_fqn(node_namespace, node_name)

    def generate_test_description() -> LaunchDescription:
        node = Node(
            package=package,
            executable=executable,
            name=node_name,
            namespace=node_namespace,
            output='screen',
            ros_arguments=ros_arguments or None,
        )
        return LaunchDescription([node, ReadyToTest()])

    class TestNodlConformance(unittest.TestCase):
        def test_conformance(self):
            assert_conforms(
                nodl_file=document,
                node_fqn=node_fqn,
                timeout_sec=timeout,
                ignore=[*rules, *ignore_from_environment(os.environ)],
            )

    module = sys._getframe(1).f_globals.get('__name__', __name__)
    for named in (generate_test_description, TestNodlConformance):
        named.__module__ = module
        named.__qualname__ = named.__name__

    return pytest.mark.launch_test(generate_test_description), TestNodlConformance
