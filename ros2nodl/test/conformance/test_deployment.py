# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0

import pytest

from nodl_schema import diff, parse_nodl
from nodl_schema.models import History, NodlDocument, ParameterDefinition, QosProfile, TopicEndpoint
from ros2nodl.configuration import ParameterValue
from ros2nodl.deployment import deployment_expectations


def _parameter(type='int', value: object = 5, **kwargs):
    return ParameterDefinition(type=type, default_value=value, **kwargs)


def _check(contract, observed, values):
    return deployment_expectations(contract, observed, values, node_fqn='/robot/node')


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
    'validator, arguments, good, bad, type_name',
    [
        ('bounds', [1, 5], 5, 6, 'int'),
        ('lt', [5], 4, 5, 'int'),
        ('gt', 1, 2, 1, 'int'),
        ('lt_eq', 5, 5, 6, 'int'),
        ('gt_eq', 1, 1, 0, 'int'),
        ('one_of', [[1, 2]], 2, 3, 'int'),
        ('fixed_size', 2, [1, 2], [1], 'int_array'),
        ('size_gt', 1, 'ab', 'a', 'string'),
        ('size_lt', 3, 'ab', 'abc', 'string'),
        ('not_empty', [], 'a', '', 'string'),
        ('unique', [], [1, 2], [1, 1], 'int_array'),
        ('subset_of', [[1, 2]], [1], [3], 'int_array'),
        ('element_bounds', [1, 5], [1, 5], [6], 'int_array'),
        ('lower_element_bounds', 1, [1], [0], 'int_array'),
        ('upper_element_bounds', 5, [5], [6], 'int_array'),
    ],
)
@pytest.mark.parametrize('suffix', ['', '<>'])
def test_builtin_constraints(validator, arguments, good, bad, type_name, suffix):
    definition = _parameter(type=type_name, value=good, validation={validator + suffix: arguments})
    contract = NodlDocument(parameters={'x': definition})
    observed = NodlDocument(parameters={'x': _parameter(type=type_name, value=good)})
    assert _check(contract, observed, {'x': ParameterValue(type_name, good)})[1] == []
    assert _check(contract, observed, {'x': ParameterValue(type_name, bad)})[1][0].kind == 'constraint_mismatch'


def test_custom_validators_and_opaque_constraints_are_unverifiable():
    contract = parse_nodl("""nodl_version: 2
parameters:
  x:
    type: int
    validation:
      custom::check: []
    additional_constraints: external constraint
""")
    _, differences = _check(contract, NodlDocument(parameters={'x': _parameter()}), {'x': ParameterValue('int', 5)})
    assert [d.kind for d in differences] == ['unverifiable', 'unverifiable']


@pytest.mark.parametrize(
    'constraints',
    [
        {'validation': {'bounds': [1, 10]}},
        {'additional_constraints': 'external constraint'},
    ],
)
def test_unavailable_unselected_constrained_value_is_unverifiable(constraints):
    contract = NodlDocument(parameters={'limit': _parameter(**constraints), 'rate': _parameter()})
    observed = NodlDocument(parameters={'limit': _parameter(value=None), 'rate': _parameter()})
    _, differences = _check(contract, observed, {'rate': ParameterValue('int', 5)})
    assert [(d.kind, d.name) for d in differences] == [('unverifiable', 'limit')]


def _qos_case(policy='reliability', value=ParameterValue('string', 'best_effort'), read_only=True):
    endpoint = TopicEndpoint(
        name='state', type='std_msgs/msg/String', qos=QosProfile(history='KEEP_LAST', depth=10, reliability='RELIABLE')
    )
    contract = NodlDocument(publishers=[endpoint])
    name = f'qos_overrides./robot/state.publisher.{policy}'
    observed = NodlDocument(
        publishers=[endpoint.copy(deep=True)],
        parameters={
            name: _parameter(type=value.type, value=value.value, read_only=read_only),
        },
    )
    return contract, observed, {name: value}


def test_permitted_override_checks_both_parameter_and_actual_endpoint_qos():
    contract, observed, values = _qos_case()
    expected, differences = _check(contract, observed, values)
    assert differences == []
    assert expected.publishers and contract.publishers and observed.publishers
    assert expected.publishers[0].qos.reliability.value == 'BEST_EFFORT'
    assert contract.publishers[0].qos.reliability.value == 'RELIABLE'
    assert diff(expected, observed.copy(update={'parameters': None}), node_fqn='/robot/node')[0].kind == 'qos_mismatch'
    observed.publishers[0].qos = expected.publishers[0].qos
    assert diff(expected, observed.copy(update={'parameters': None}), node_fqn='/robot/node') == []


@pytest.mark.parametrize(
    'policy,value',
    [
        ('depth', ParameterValue('int', 3)),
        ('history', ParameterValue('string', 'keep_all')),
        ('durability', ParameterValue('string', 'transient_local')),
        ('liveliness', ParameterValue('string', 'automatic')),
        ('deadline', ParameterValue('int', 500)),
        ('lifespan', ParameterValue('int', 1000)),
        ('liveliness_lease_duration', ParameterValue('int', 2000)),
    ],
)
def test_standard_observable_qos_overrides(policy, value):
    assert _check(*_qos_case(policy, value))[1] == []


@pytest.mark.parametrize(
    'policy,value',
    [
        ('unknown', ParameterValue('int', 1)),
        ('avoid_ros_namespace_conventions', ParameterValue('bool', True)),
        ('depth', ParameterValue('int', -1)),
        ('reliability', ParameterValue('string', 'RELIABLE')),
        ('reliability', ParameterValue('string', 'invalid')),
    ],
)
def test_rejected_qos_override_values(policy, value):
    assert _check(*_qos_case(policy, value))[1][0].kind == 'configuration_error'


def test_override_requires_exposed_read_only_parameter_and_known_target():
    contract, observed, values = _qos_case(read_only=False)
    assert _check(contract, observed, values)[1][0].kind == 'configuration_error'
    observed.parameters = None
    assert _check(contract, observed, values)[1][0].kind == 'configuration_error'
    contract, observed, values = _qos_case()
    contract.publishers = None
    assert _check(contract, observed, values)[1][0].kind == 'configuration_error'


def test_depth_override_is_checked_with_system_default_history():
    contract, observed, values = _qos_case('depth', ParameterValue('int', 3))
    assert contract.publishers and observed.publishers
    contract.publishers[0].qos.history = History.SYSTEM_DEFAULT
    assert _check(contract, observed, values)[1][0].kind == 'qos_mismatch'
    observed.publishers[0].qos.depth = 3
    assert _check(contract, observed, values)[1] == []
    observed.publishers[0].qos.history = History.SYSTEM_DEFAULT
    observed.publishers[0].qos.depth = None
    assert _check(contract, observed, values)[1][0].kind == 'unverifiable'


def test_history_override_does_not_invent_a_depth_expectation():
    contract, observed, values = _qos_case('history', ParameterValue('string', 'keep_last'))
    assert contract.publishers
    contract.publishers[0].qos.history = History.SYSTEM_DEFAULT
    contract.publishers[0].qos.depth = None
    expected, differences = _check(contract, observed, values)
    assert differences == []
    assert diff(expected, observed.copy(update={'parameters': None}), node_fqn='/robot/node') == []
