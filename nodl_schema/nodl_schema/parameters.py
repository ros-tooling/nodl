# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Validation helpers for ROS parameter names."""

from collections.abc import Iterable


def validate_parameter_namespaces(parameters: Iterable[str]) -> str | None:
    """Validate that the set of parameter names, returning an error message if validation fails."""
    conflict = find_parameter_namespace_conflict(parameters)
    if conflict is not None:
        parameter, nested_parameter = conflict
        return f'parameter {parameter!r} conflicts with {nested_parameter!r}: a parameter cannot also be a parameter namespace'

    return None


def find_parameter_namespace_conflict(names: Iterable[str]) -> tuple[str, str] | None:
    """Return the first parameter pair where one name is the other's namespace.

    Parameters with a common namespace are valid, such as ``colour.r`` and
    ``colour.g``.
    A parameter cannot also be a namespace, so ``colour`` and ``colour.r``
    conflict.
    """
    names_set = set(names)
    for name in sorted(names_set):
        parts = name.split('.')
        for part_count in range(1, len(parts)):
            namespace = '.'.join(parts[:part_count])
            if namespace in names_set:
                return namespace, name
    return None
