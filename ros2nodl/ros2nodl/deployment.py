# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Pure deployment-aware checks over a contract, expectations, and observation."""

from __future__ import annotations

import math
import operator
import re
from collections.abc import Mapping

from nodl_schema import Difference
from nodl_schema.models import Durability, History, Liveliness, NodlDocument, Reliability
from nodl_schema.parameters import parse_parameter_type
from ros2nodl.configuration import ParameterValue
from ros2nodl.infrastructure import is_hidden_parameter

_QOS_PARAMETER = re.compile(r'^qos_overrides\.(?P<topic>/[^.]+)\.(?P<kind>publisher|subscription)\.(?P<policy>\w+)$')
_POLICIES = {'history': History, 'reliability': Reliability, 'durability': Durability, 'liveliness': Liveliness}
_DURATIONS = {
    'deadline': 'deadline_ns',
    'lifespan': 'lifespan_ns',
    'liveliness_lease_duration': 'liveliness_lease_duration_ns',
}


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


def _validator_accepts(name, arguments, value):
    args = arguments if isinstance(arguments, list) else [arguments]
    comparisons = {'lt': operator.lt, 'gt': operator.gt, 'lt_eq': operator.le, 'gt_eq': operator.ge}
    if name in comparisons:
        return comparisons[name](value, args[0])
    if name == 'bounds':
        return args[0] <= value <= args[1]
    if name == 'one_of':
        return value in args[0]
    if name == 'fixed_size':
        return len(value) == args[0]
    if name == 'size_gt':
        return len(value) > args[0]
    if name == 'size_lt':
        return len(value) < args[0]
    if name == 'not_empty':
        return bool(value)
    if name == 'unique':
        return len(value) == len(set(value))
    if name == 'subset_of':
        return all(item in args[0] for item in value)
    if name == 'element_bounds':
        return all(args[0] <= item <= args[1] for item in value)
    if name == 'lower_element_bounds':
        return all(item >= args[0] for item in value)
    if name == 'upper_element_bounds':
        return all(item <= args[0] for item in value)
    return None


def _constraints(name, definition, value, source):
    differences = []
    parsed = parse_parameter_type(_type_name(definition))
    if parsed.fixed_size is not None and len(value) > parsed.fixed_size:
        differences.append(_difference('constraint_mismatch', name, f'{source}: exceeds capacity {parsed.fixed_size}'))
    if definition.additional_constraints:
        differences.append(_difference('unverifiable', name, 'additional_constraints is opaque metadata'))
    validators = definition.validation.dict(by_alias=True, exclude_unset=True) if definition.validation else {}
    for validator, arguments in validators.items():
        accepted = _validator_accepts(validator.removesuffix('<>'), arguments, value)
        if accepted is None:
            differences.append(_difference('unverifiable', name, f'unsupported validator {validator!r}'))
        elif not accepted:
            differences.append(
                _difference('constraint_mismatch', name, f'{source}: violates {validator!r} {arguments!r}')
            )
    return differences


def _resolve_topic(name, node_fqn):
    if name.startswith('/'):
        return name
    if name.startswith('~'):
        return node_fqn + '/' + name[1:].lstrip('/')
    return node_fqn.rsplit('/', 1)[0] + '/' + name


def _qos_override(expected, observed, name, value, node_fqn):
    match = _QOS_PARAMETER.fullmatch(name)
    if match is None:
        return [_difference('configuration_error', name, 'unsupported QoS override target or endpoint identifier')]
    parameter = (observed.parameters or {}).get(name)
    if parameter is None or parameter.read_only is not True:
        return [_difference('configuration_error', name, 'QoS override is not exposed as a read-only parameter')]
    section = match['kind'] + 's'
    targets = [ep for ep in getattr(expected, section) or [] if _resolve_topic(ep.name, node_fqn) == match['topic']]
    if len(targets) != 1:
        return [_difference('configuration_error', name, 'QoS override must select one declared endpoint')]
    policy = match['policy']
    try:
        if match['kind'] == 'subscription' and policy == 'lifespan':
            raise ValueError('lifespan is not a subscription override policy')
        if policy in _POLICIES:
            if value.type != 'string' or value.value != value.value.lower():
                raise ValueError('policy must be a lowercase ROS policy string')
            field, converted = policy, _POLICIES[policy](value.value.upper())
        elif policy == 'depth' or policy in _DURATIONS:
            if value.type != 'int' or value.value < 0:
                raise ValueError('policy must be a nonnegative integer')
            if policy == 'depth' and value.value == 0:
                raise ValueError('depth must be a positive integer')
            field, converted = _DURATIONS.get(policy, policy), value.value
        else:
            raise ValueError('policy is not observable in the NoDL QoS model')
    except ValueError as exc:
        return [_difference('configuration_error', name, str(exc))]
    # Update only the copied deployment expectation; contract and observation stay intact.
    targets[0].qos = targets[0].qos.copy(update={field: converted})
    return []


def deployment_expectations(
    contract: NodlDocument,
    observed: NodlDocument,
    expectations: Mapping[str, ParameterValue],
    *,
    node_fqn: str,
) -> tuple[NodlDocument, list[Difference]]:
    """Derive expected QoS and check explicit values and constraints at observation time.

    The observation adapter stores current values in ``ParameterDefinition.default_value``.
    Only that boundary is read here; contract defaults never become expectations.
    """
    expected = contract.copy(deep=True)
    differences = []
    for name, value in expectations.items():
        if name.startswith('qos_overrides.'):
            differences.extend(_qos_override(expected, observed, name, value, node_fqn))
            definition = None
        else:
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
        if definition:
            differences.extend(_constraints(name, definition, value.value, 'deployment value'))
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
            if definition and not _equal(value.value, actual.default_value):
                differences.extend(_constraints(name, definition, actual.default_value, 'observed value'))
    for name, definition in (contract.parameters or {}).items():
        if name in expectations:
            continue
        actual = (observed.parameters or {}).get(name)
        if actual is not None and _type_name(actual) == parse_parameter_type(_type_name(definition)).unfixed_name:
            if actual.default_value is not None:
                differences.extend(_constraints(name, definition, actual.default_value, 'observed value'))
            elif (
                definition.validation
                or definition.additional_constraints
                or parse_parameter_type(_type_name(definition)).fixed_size is not None
            ):
                differences.append(
                    _difference('unverifiable', name, 'current value is unavailable; cannot check constraints')
                )
    # A SYSTEM_DEFAULT history does not constrain the selected policy, but an explicit
    # depth still constrains a concrete KEEP_LAST endpoint.
    rejected = {d.name for d in differences if d.kind == 'configuration_error'}
    for name, value in expectations.items():
        match = _QOS_PARAMETER.fullmatch(name)
        if not match or match['policy'] != 'depth' or name in rejected:
            continue
        section = match['kind'] + 's'
        target = next(ep for ep in getattr(expected, section) if _resolve_topic(ep.name, node_fqn) == match['topic'])
        if target.qos.history != History.SYSTEM_DEFAULT:
            continue
        endpoints = [
            ep for ep in getattr(observed, section) or [] if _resolve_topic(ep.name, node_fqn) == match['topic']
        ]
        for endpoint in endpoints:
            if endpoint.qos.history == History.KEEP_ALL:
                continue
            if endpoint.qos.depth is None:
                differences.append(
                    Difference('unverifiable', section, match['topic'], 'depth: observed value is unknown')
                )
            elif endpoint.qos.depth != value.value:
                differences.append(
                    Difference(
                        'qos_mismatch',
                        section,
                        match['topic'],
                        f'depth: expected {value.value}, got {endpoint.qos.depth}',
                    )
                )
    return expected, differences
