# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Semantic validation helpers for ROS parameter definitions."""

from __future__ import annotations

from collections.abc import Callable, Collection, Iterable, Mapping
from typing import Any, NamedTuple


def validate_parameter_names(parameters: Iterable[str]) -> str | None:
    """Validate parameter names, returning an error message if validation fails."""
    parameter_names = list(parameters)
    for name in parameter_names:
        if any(not part for part in name.split('.')):
            return f'invalid dotted parameter name {name!r}: name components cannot be empty'

    conflict = find_parameter_namespace_conflict(parameter_names)
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


class ParameterType(NamedTuple):
    """A parameter ``type`` string split into its parts."""

    base: str
    is_array: bool
    fixed_size: int | None

    @property
    def unfixed_name(self) -> str:
        """The type name without its fixed size, such as ``int_array`` for ``int_array_fixed_3``."""
        return f'{self.base}_array' if self.is_array else self.base


def parse_parameter_type(type_name: str) -> ParameterType:
    """Parse a schema-valid parameter type, such as ``double_array_fixed_3``."""
    name, _, size = type_name.partition('_fixed_')
    is_array = name.endswith('_array')
    return ParameterType(
        base=name.removesuffix('_array'),
        is_array=is_array,
        fixed_size=int(size) if size else None,
    )


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


_BASE_TYPE_CHECKS: dict[str, Callable[[Any], bool]] = {
    'bool': lambda value: isinstance(value, bool),
    'int': _is_int,
    'double': lambda value: _is_int(value) or isinstance(value, float),
    'string': lambda value: isinstance(value, str),
    'byte': lambda value: _is_int(value) and 0 <= value <= 255,
}


def _matches_base_type(value: Any, base: str) -> bool:
    """Return whether a single value is valid for a parameter base type; ``none`` matches nothing."""
    return _BASE_TYPE_CHECKS.get(base, lambda _: False)(value)


def _takes_value(t: ParameterType) -> bool:
    return t.base != 'none'


def _is_scalar(t: ParameterType) -> bool:
    return _takes_value(t) and not t.is_array


def _is_numeric_scalar(t: ParameterType) -> bool:
    return t.base in {'int', 'double'} and not t.is_array


def _is_sized(t: ParameterType) -> bool:
    return t.is_array or t.base == 'string'


def _is_numeric_array(t: ParameterType) -> bool:
    return t.base in {'int', 'double', 'byte'} and t.is_array


def _no_values(arguments: Any) -> list:
    del arguments
    return []


def _as_list(arguments: Any) -> list:
    return arguments if isinstance(arguments, list) else [arguments]


def _first(arguments: list) -> list:
    return arguments[0]


class _Validator(NamedTuple):
    applies_to: Callable[[ParameterType], bool]
    # The values a validator compares the parameter (or its elements) against.
    values: Callable[[Any], list]
    is_range: bool = False
    # Validators that may not be combined with this one on the same parameter.
    excludes: tuple[str, ...] = ()


_SCALAR_BOUNDS = ('lt', 'gt', 'lt_eq', 'gt_eq')
_ELEMENT_BOUNDS = ('lower_element_bounds', 'upper_element_bounds')

# Built-in validators by base name (without the optional ``<>`` suffix).
_VALIDATORS: dict[str, _Validator] = {
    'bounds': _Validator(_is_numeric_scalar, _as_list, is_range=True, excludes=_SCALAR_BOUNDS),
    'lt': _Validator(_is_numeric_scalar, _as_list),
    'gt': _Validator(_is_numeric_scalar, _as_list),
    'lt_eq': _Validator(_is_numeric_scalar, _as_list),
    'gt_eq': _Validator(_is_numeric_scalar, _as_list),
    'one_of': _Validator(_is_scalar, _first),
    'fixed_size': _Validator(_is_sized, _no_values),
    'size_gt': _Validator(_is_sized, _no_values),
    'size_lt': _Validator(_is_sized, _no_values),
    'not_empty': _Validator(_is_sized, _no_values),
    'unique': _Validator(lambda t: t.is_array, _no_values),
    'subset_of': _Validator(lambda t: t.is_array, _first),
    'element_bounds': _Validator(_is_numeric_array, _as_list, is_range=True, excludes=_ELEMENT_BOUNDS),
    'lower_element_bounds': _Validator(_is_numeric_array, _as_list),
    'upper_element_bounds': _Validator(_is_numeric_array, _as_list),
}


def _check_default_value(param_type: ParameterType, type_name: str, default: Any) -> str | None:
    """Check that a default value matches its declared parameter type."""
    if not _takes_value(param_type):
        return f'type {type_name!r} does not take a default_value'

    if param_type.is_array:
        if not isinstance(default, list):
            return f'default_value {default!r} is not a list, as type {type_name!r} requires'
        for element in default:
            if not _matches_base_type(element, param_type.base):
                return f'default_value element {element!r} does not match type {type_name!r}'
    elif not _matches_base_type(default, param_type.base):
        return f'default_value {default!r} does not match type {type_name!r}'

    if param_type.fixed_size is not None and len(default) > param_type.fixed_size:
        return f'default_value has length {len(default)}, more than type {type_name!r} allows'

    return None


class _AuthoredValidator(NamedTuple):
    """A built-in validator as written on a parameter."""

    base: str
    name: str
    arguments: Any


def _check_validator(param_type: ParameterType, type_name: str, authored: _AuthoredValidator) -> str | None:
    """Check that a built-in validator applies to the parameter type, with matching arguments."""
    validator, validator_name, arguments = _VALIDATORS[authored.base], authored.name, authored.arguments
    if not validator.applies_to(param_type):
        return f'validator {validator_name!r} does not apply to type {type_name!r}'

    for value in validator.values(arguments):
        if not _matches_base_type(value, param_type.base):
            return f'validator {validator_name!r} argument {value!r} does not match type {type_name!r}'

    if validator.is_range:
        lower, upper = arguments
        if lower > upper:
            return f'validator {validator_name!r} lower bound {lower!r} is greater than upper bound {upper!r}'

    return None


def _check_validator_combinations(validators: Collection[_AuthoredValidator]) -> str | None:
    """Check that no two built-in validators on one parameter exclude each other."""
    for validator in validators:
        for other in validators:
            if other.base in _VALIDATORS[validator.base].excludes:
                return f'validator {validator.name!r} cannot be combined with {other.name!r}'
    return None


def _check_parameter_definition(definition: Mapping[str, Any]) -> str | None:
    type_name = definition['type']
    param_type = parse_parameter_type(type_name)
    if 'default_value' in definition and (
        error := _check_default_value(param_type, type_name, definition['default_value'])
    ):
        return error

    # Custom, namespace-qualified validators are not checked.
    validators = [
        _AuthoredValidator(name.removesuffix('<>'), name, arguments)
        for name, arguments in (definition.get('validation') or {}).items()
        if '::' not in name
    ]
    for validator in validators:
        if error := _check_validator(param_type, type_name, validator):
            return error

    return _check_validator_combinations(validators)


def validate_parameter_definitions(parameters: Mapping[str, Mapping[str, Any]]) -> str | None:
    """Validate schema-valid parameter definitions, returning an error message for the first invalid one.

    These are the semantic checks kept out of the JSON Schema:
    the ``default_value`` must match ``type``,
    each built-in validator must apply to ``type`` with arguments of the parameter's element type,
    and no two built-in validators may exclude each other, such as ``bounds`` with ``lt``.
    """
    for name, definition in parameters.items():
        if error := _check_parameter_definition(definition):
            return f'parameter {name!r}: {error}'
    return None
