# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Helpers that keep the typed parameters of a generated node independent of the listener's storage."""

import copy
import math
from typing import Any

_STAMP = 'stamp_'


def _is_struct(value: Any) -> bool:
    return hasattr(value, '__dict__') and not callable(value)


def _field_names(params: Any) -> list[str]:
    """Return the names of the parameter values of ``params``, which excludes the update stamp and methods."""
    return [
        name
        for name in dir(params)
        if not name.startswith('_') and name != _STAMP and not callable(getattr(params, name))
    ]


def copy_parameters(params: Any) -> Any:
    """Return a copy of ``params`` that shares no object with it, nested structs and lists included.

    ``generate_parameter_library_py`` stores a nested struct as a class attribute, so copying one of its parameter objects shares the nested struct.
    The returned copy owns each nested struct and keeps the update stamp.
    """
    result = copy.copy(params)
    for name in _field_names(params):
        value = getattr(params, name)
        setattr(result, name, copy_parameters(value) if _is_struct(value) else copy.deepcopy(value))
    return result


def parameter_values(params: Any) -> dict[str, Any]:
    """Return the values of ``params`` as a nested dict that shares no object with it and has no update stamp."""
    return {
        name: parameter_values(value) if _is_struct(value) else copy.deepcopy(value)
        for name in _field_names(params)
        for value in [getattr(params, name)]
    }


def values_equal(first: Any, second: Any) -> bool:
    """Return whether two values from `parameter_values` are equal, treating NaN as equal to NaN."""
    if isinstance(first, dict) and isinstance(second, dict):
        return first.keys() == second.keys() and all(values_equal(first[key], second[key]) for key in first)
    if isinstance(first, (list, tuple)) and isinstance(second, (list, tuple)):
        return len(first) == len(second) and all(values_equal(a, b) for a, b in zip(first, second))
    if isinstance(first, float) and isinstance(second, float) and math.isnan(first) and math.isnan(second):
        return True
    return bool(first == second)
