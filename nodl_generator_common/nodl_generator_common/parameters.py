# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Parameter transformations shared by code generators."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from nodl_schema.parameters import validate_parameter_names

T = TypeVar('T')


def nest_dotted_parameters(parameters: Mapping[str, T]) -> dict[str, Any]:
    """Expand flat dotted parameter names into a nested, ordered mapping.

    ``generate_parameter_library`` uses nested mappings to generate dotted ROS
    parameter names and nested typed accessors.
    Input values are retained without copying.
    """
    if error := validate_parameter_names(parameters):
        raise ValueError(error)

    nested: dict[str, Any] = {}
    for name, value in parameters.items():
        parts = name.split('.')
        branch = nested
        for part in parts[:-1]:
            child = branch.setdefault(part, {})
            branch = cast(dict[str, Any], child)
        branch[parts[-1]] = value
    return nested
