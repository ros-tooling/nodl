# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Pure semantic diff for two NoDL node-interface documents."""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from enum import Enum

from nodl_schema.models import NodlDocument, ParameterDefinition, QosProfile

_SECTION_ORDER = {
    'publishers': 0,
    'subscriptions': 1,
    'service_servers': 2,
    'service_clients': 3,
    'action_servers': 4,
    'action_clients': 5,
    'parameters': 6,
}
_TYPE_NAMESPACE = {
    'publishers': 'msg',
    'subscriptions': 'msg',
    'service_servers': 'srv',
    'service_clients': 'srv',
    'action_servers': 'action',
    'action_clients': 'action',
}
_SELECTION_POLICIES = {'SYSTEM_DEFAULT', 'BEST_AVAILABLE'}
_NODE_FQN = re.compile(r'^/[A-Za-z][A-Za-z0-9_/]*[A-Za-z0-9_]$|^/[A-Za-z]$')


@dataclass(frozen=True)
class Difference:
    """One stable semantic difference between expected and actual NoDL documents."""

    kind: str
    section: str
    name: str
    detail: str

    def __str__(self) -> str:
        return f'[{self.kind}] {self.section} {self.name!r}: {self.detail}'


def _value(value):
    return value.value if isinstance(value, Enum) else value


def _type_name(value) -> str:
    return str(_value(value))


def _normalize_type(type_name: str, section: str) -> str:
    parts = type_name.split('/')
    if len(parts) == 2:
        return f'{parts[0]}/{_TYPE_NAMESPACE[section]}/{parts[1]}'
    return type_name


def _validate_node_fqn(node_fqn: str) -> None:
    if not isinstance(node_fqn, str) or not _NODE_FQN.fullmatch(node_fqn) or '//' in node_fqn:
        raise ValueError(f'node_fqn must be a fully qualified ROS node name, got {node_fqn!r}')


def _resolve_name(name: str, node_fqn: str) -> str:
    if name.startswith('/'):
        return name
    if name.startswith('~'):
        suffix = name[1:].lstrip('/')
        return f'{node_fqn}/{suffix}'
    namespace = node_fqn.rsplit('/', 1)[0]
    return f'{namespace}/{name}' if namespace else f'/{name}'


def _difference(kind: str, section: str, name: str, detail: str) -> Difference:
    return Difference(kind=kind, section=section, name=name, detail=detail)


def _identity_groups(endpoints: Iterable, section: str, node_fqn: str) -> dict[str, dict[str, object]]:
    groups: dict[str, dict[str, object]] = defaultdict(dict)
    for endpoint in endpoints:
        name = _resolve_name(endpoint.name, node_fqn)
        type_name = _normalize_type(endpoint.type, section)
        groups[name].setdefault(type_name, endpoint)
    return groups


def _policy_difference(
    *,
    expected,
    actual,
    field: str,
    section: str,
    name: str,
) -> Difference | None:
    expected_value = _value(expected)
    actual_value = _value(actual)
    if expected_value is None or expected_value in _SELECTION_POLICIES:
        return None
    if actual_value is None or actual_value in _SELECTION_POLICIES:
        return _difference(
            'unverifiable',
            section,
            name,
            f'{field}: expected {expected_value}, observed value is unknown',
        )
    if expected_value != actual_value:
        return _difference('qos_mismatch', section, name, f'{field}: expected {expected_value}, got {actual_value}')
    return None


def _duration_difference(
    *,
    expected: int | None,
    actual: int | None,
    field: str,
    section: str,
    name: str,
) -> Difference | None:
    if expected is None:
        return None
    expected_value = expected or None
    actual_value = actual or None
    if expected_value == actual_value:
        return None
    return _difference('qos_mismatch', section, name, f'{field}: expected {expected_value}, got {actual_value}')


def _qos_differences(
    expected: QosProfile,
    actual: QosProfile | None,
    section: str,
    name: str,
) -> list[Difference]:
    if actual is None:
        return [_difference('unverifiable', section, name, 'declared QoS is not observable')]

    differences = []
    for field in ('history', 'reliability', 'durability', 'liveliness'):
        difference = _policy_difference(
            expected=getattr(expected, field),
            actual=getattr(actual, field),
            field=field,
            section=section,
            name=name,
        )
        if difference is not None:
            differences.append(difference)

    if _value(expected.history) == 'KEEP_LAST':
        if actual.depth is None:
            differences.append(_difference('unverifiable', section, name, 'depth: observed value is unknown'))
        elif expected.depth != actual.depth:
            differences.append(
                _difference('qos_mismatch', section, name, f'depth: expected {expected.depth}, got {actual.depth}')
            )

    for field in ('deadline_ns', 'lifespan_ns', 'liveliness_lease_duration_ns'):
        difference = _duration_difference(
            expected=getattr(expected, field),
            actual=getattr(actual, field),
            field=field,
            section=section,
            name=name,
        )
        if difference is not None:
            differences.append(difference)
    return differences


def _endpoint_differences(
    expected: Iterable,
    actual: Iterable,
    section: str,
    node_fqn: str,
    compare_properties: Callable[[object, object, str, str], list[Difference]],
) -> list[Difference]:
    expected_groups = _identity_groups(expected, section, node_fqn)
    actual_groups = _identity_groups(actual, section, node_fqn)
    differences = []

    for name in sorted(set(expected_groups) | set(actual_groups)):
        expected_types = expected_groups.get(name, {})
        actual_types = actual_groups.get(name, {})
        missing_types = sorted(set(expected_types) - set(actual_types))
        extra_types = sorted(set(actual_types) - set(expected_types))

        if len(missing_types) == 1 and len(extra_types) == 1:
            differences.append(
                _difference(
                    'type_mismatch',
                    section,
                    name,
                    f'expected {missing_types[0]!r}, got {extra_types[0]!r}',
                )
            )
        else:
            differences.extend(
                _difference('missing', section, name, f'expected type {type_name!r} was not observed')
                for type_name in missing_types
            )
            differences.extend(
                _difference('extra', section, name, f'observed undeclared type {type_name!r}')
                for type_name in extra_types
            )

        for type_name in sorted(set(expected_types) & set(actual_types)):
            differences.extend(compare_properties(expected_types[type_name], actual_types[type_name], section, name))
    return differences


def _topic_properties(expected, actual, section: str, name: str) -> list[Difference]:
    return _qos_differences(expected.qos, actual.qos, section, name)


def _service_properties(expected, actual, section: str, name: str) -> list[Difference]:
    if expected.qos is None:
        return []
    return _qos_differences(expected.qos, actual.qos, section, name)


def _no_properties(expected, actual, section: str, name: str) -> list[Difference]:
    del expected, actual, section, name
    return []


def _is_fixed_type(type_name: str) -> bool:
    return '_fixed_' in type_name


def _fixed_base_type(type_name: str) -> str:
    return type_name.split('_fixed_', 1)[0]


def _parameter_differences(
    expected: dict[str, ParameterDefinition],
    actual: dict[str, ParameterDefinition],
) -> list[Difference]:
    differences = []
    for name in sorted(set(expected) | set(actual)):
        if name not in actual:
            differences.append(_difference('missing', 'parameters', name, 'declared parameter was not observed'))
            continue
        if name not in expected:
            differences.append(_difference('extra', 'parameters', name, 'observed undeclared parameter'))
            continue

        expected_parameter = expected[name]
        actual_parameter = actual[name]
        expected_type = _type_name(expected_parameter.type)
        actual_type = _type_name(actual_parameter.type)
        if expected_type != actual_type:
            if _is_fixed_type(expected_type) and _fixed_base_type(expected_type) == actual_type:
                differences.append(
                    _difference(
                        'unverifiable',
                        'parameters',
                        name,
                        f'fixed-size type {expected_type!r} cannot be proven from observed type {actual_type!r}',
                    )
                )
            else:
                differences.append(
                    _difference(
                        'type_mismatch',
                        'parameters',
                        name,
                        f'expected {expected_type!r}, got {actual_type!r}',
                    )
                )

        expected_read_only = expected_parameter.read_only
        actual_read_only = actual_parameter.read_only
        if expected_read_only is not None:
            if actual_read_only is None:
                differences.append(
                    _difference('unverifiable', 'parameters', name, 'read_only: observed value is unknown')
                )
            elif expected_read_only != actual_read_only:
                differences.append(
                    _difference(
                        'property_mismatch',
                        'parameters',
                        name,
                        f'read_only: expected {expected_read_only}, got {actual_read_only}',
                    )
                )
    return differences


def _sort_key(difference: Difference) -> tuple:
    return (
        _SECTION_ORDER.get(difference.section, len(_SECTION_ORDER)),
        difference.name,
        difference.kind,
        difference.detail,
    )


def diff(expected: NodlDocument, actual: NodlDocument, *, node_fqn: str) -> list[Difference]:
    """Return stable semantic differences between declared and observed NoDL documents."""
    if not isinstance(expected, NodlDocument) or not isinstance(actual, NodlDocument):
        raise TypeError('expected and actual must be NodlDocument objects')
    _validate_node_fqn(node_fqn)

    differences = []
    for section in ('publishers', 'subscriptions'):
        differences.extend(
            _endpoint_differences(
                getattr(expected, section) or [],
                getattr(actual, section) or [],
                section,
                node_fqn,
                _topic_properties,
            )
        )
    for section in ('service_servers', 'service_clients'):
        differences.extend(
            _endpoint_differences(
                getattr(expected, section) or [],
                getattr(actual, section) or [],
                section,
                node_fqn,
                _service_properties,
            )
        )
    for section in ('action_servers', 'action_clients'):
        differences.extend(
            _endpoint_differences(
                getattr(expected, section) or [],
                getattr(actual, section) or [],
                section,
                node_fqn,
                _no_properties,
            )
        )
    differences.extend(_parameter_differences(expected.parameters or {}, actual.parameters or {}))
    return sorted(differences, key=_sort_key)
