# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0

import pytest

from nodl_schema.models import NodlDocument, ParameterDefinition
from ros2nodl.configuration import ParameterValue
from ros2nodl.deployment import deployment_expectations


def _parameter(type='int', value: object = 5, **kwargs):
    return ParameterDefinition(type=type, default_value=value, **kwargs)


def _check(contract, observed, values):
    return deployment_expectations(contract, observed, values)


@pytest.mark.parametrize('read_only', [True, False])
def test_explicit_snapshot_equality_is_independent_of_contract_default(read_only):
    contract = NodlDocument(parameters={'rate': _parameter(value=1, read_only=read_only)})
    observed = NodlDocument(parameters={'rate': _parameter(read_only=read_only)})
    expected, differences = _check(contract, observed, {'rate': ParameterValue('int', 5)})
    assert differences == []
    assert contract.parameters is not None and expected.parameters is not None
    assert contract.parameters['rate'].default_value == 1
    assert expected.parameters['rate'].default_value == 1
    _, differences = _check(contract, observed, {'rate': ParameterValue('int', 7)})
    assert [d.kind for d in differences] == ['value_mismatch']


@pytest.mark.parametrize(
    'actual, value, kind',
    [
        (_parameter(type='bool', value=True), ParameterValue('int', 1), 'type_mismatch'),
        (_parameter(value=None), ParameterValue('int', 5), 'unverifiable'),
        (None, ParameterValue('int', 5), 'missing'),
        (_parameter(), ParameterValue('bool', True), 'type_mismatch'),
    ],
)
def test_missing_unknown_and_wrong_types(actual, value, kind):
    _, differences = _check(
        NodlDocument(parameters={'x': _parameter()}),
        NodlDocument(parameters={'x': actual} if actual else {}),
        {'x': value},
    )
    assert differences[0].kind == kind


def test_undeclared_explicit_parameter_cannot_be_ignored():
    _, differences = _check(NodlDocument(), NodlDocument(), {'typo': ParameterValue('int', 5)})
    assert differences[0].kind == 'configuration_error'


@pytest.mark.parametrize(
    'type_name,value',
    [('double', float('nan')), ('double_array', [float('nan'), 2.0]), ('string_array', ['a\nb', '🤖'])],
)
def test_array_and_nan_snapshot_equality(type_name, value):
    contract = NodlDocument(parameters={'x': _parameter(type=type_name, value=value)})
    observed = NodlDocument(parameters={'x': _parameter(type=type_name, value=value)})
    assert _check(contract, observed, {'x': ParameterValue(type_name, value)})[1] == []
