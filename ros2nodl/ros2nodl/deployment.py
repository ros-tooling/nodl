# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Compare explicit parameter expectations with a running node's current values."""

from __future__ import annotations

import math
from collections.abc import Mapping

from nodl_schema import Difference
from nodl_schema.models import NodlDocument
from nodl_schema.parameters import parse_parameter_type
from ros2nodl.configuration import ParameterValue
from ros2nodl.infrastructure import is_hidden_parameter


def _difference(kind, name, detail):
    return Difference(kind, 'parameters', name, detail)


def _type_name(parameter):
    return getattr(parameter.type, 'value', parameter.type)


def _equal(left, right):
    if isinstance(left, float) and isinstance(right, float) and math.isnan(left) and math.isnan(right):
        return True
    if isinstance(left, list) and isinstance(right, list):
        return len(left) == len(right) and all(_equal(a, b) for a, b in zip(left, right))
    return left == right


def deployment_expectations(
    contract: NodlDocument,
    observed: NodlDocument,
    expectations: Mapping[str, ParameterValue],
) -> tuple[NodlDocument, list[Difference]]:
    """Check explicit parameter types and values at observation time.

    The observation adapter stores current values in ``ParameterDefinition.default_value``.
    Only that boundary is read here; contract defaults never become expectations.
    """
    differences = []
    for name, value in expectations.items():
        definition = (contract.parameters or {}).get(name)
        # Framework parameters can be explicit expectations without joining the public interface.
        if definition is None and not is_hidden_parameter(name):
            differences.append(_difference('configuration_error', name, 'deployment parameter is undeclared'))
            continue
        actual = (observed.parameters or {}).get(name)
        expected_type = parse_parameter_type(_type_name(definition)).unfixed_name if definition else value.type
        if value.type != expected_type:
            differences.append(
                _difference(
                    'type_mismatch', name, f'deployment expects {value.type!r}, contract requires {expected_type!r}'
                )
            )
            continue
        if actual is None:
            differences.append(_difference('missing', name, 'explicit deployment parameter was not observed'))
        elif _type_name(actual) != value.type:
            differences.append(
                _difference(
                    'type_mismatch', name, f'deployment expects {value.type!r}, observed {_type_name(actual)!r}'
                )
            )
        elif actual.default_value is None:
            differences.append(_difference('unverifiable', name, 'current parameter value is unavailable'))
        else:
            if not _equal(value.value, actual.default_value):
                differences.append(
                    _difference(
                        'value_mismatch',
                        name,
                        f'expected deployment value {value.value!r}, observed {actual.default_value!r}',
                    )
                )
    return contract, differences
