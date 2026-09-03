# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""ROS-free tests for the NoDL semantic diff."""

import pytest

from nodl_schema import Difference, diff
from nodl_schema.models import (
    ActionEndpoint,
    Durability,
    History,
    Liveliness,
    NodlDocument,
    ParameterDefinition,
    QosProfile,
    Reliability,
    ServiceEndpoint,
    TopicEndpoint,
)


def _qos(
    *,
    history=History.KEEP_LAST,
    depth=10,
    reliability=Reliability.RELIABLE,
    durability=Durability.VOLATILE,
    deadline_ns=None,
    lifespan_ns=None,
    liveliness=Liveliness.AUTOMATIC,
    liveliness_lease_duration_ns=None,
):
    return QosProfile(
        history=history,
        depth=depth,
        reliability=reliability,
        durability=durability,
        deadline_ns=deadline_ns,
        lifespan_ns=lifespan_ns,
        liveliness=liveliness,
        liveliness_lease_duration_ns=liveliness_lease_duration_ns,
    )


def _topic(name='/topic', type='std_msgs/msg/String', qos=None):
    return TopicEndpoint(name=name, type=type, qos=qos or _qos())


def _service(name='/service', type='std_srvs/srv/Trigger', qos=None):
    return ServiceEndpoint(name=name, type=type, qos=qos)


def _action(name='/action', type='example_interfaces/action/Fibonacci'):
    return ActionEndpoint(name=name, type=type)


def _document(**sections):
    return NodlDocument(nodl_version=2, **sections)


def _kinds(differences):
    return [difference.kind for difference in differences]


def test_empty_and_missing_collections_are_equal():
    assert diff(_document(), _document(publishers=[]), node_fqn='/node') == []


@pytest.mark.parametrize(
    'section,endpoint',
    [
        ('publishers', _topic()),
        ('subscriptions', _topic()),
        ('service_servers', _service()),
        ('service_clients', _service()),
        ('action_servers', _action()),
        ('action_clients', _action()),
    ],
)
def test_all_endpoint_sections_report_missing_and_extra(section, endpoint):
    missing = diff(_document(**{section: [endpoint]}), _document(), node_fqn='/node')
    extra = diff(_document(), _document(**{section: [endpoint]}), node_fqn='/node')

    assert [(item.kind, item.section) for item in missing] == [('missing', section)]
    assert [(item.kind, item.section) for item in extra] == [('extra', section)]


@pytest.mark.parametrize(
    'section,expected,actual',
    [
        ('publishers', _topic(type='std_msgs/msg/String'), _topic(type='std_msgs/msg/Int32')),
        ('subscriptions', _topic(type='std_msgs/msg/String'), _topic(type='std_msgs/msg/Int32')),
        (
            'service_servers',
            _service(type='std_srvs/srv/Trigger'),
            _service(type='std_srvs/srv/SetBool'),
        ),
        (
            'service_clients',
            _service(type='std_srvs/srv/Trigger'),
            _service(type='std_srvs/srv/SetBool'),
        ),
        (
            'action_servers',
            _action(type='example_interfaces/action/Fibonacci'),
            _action(type='nav2_msgs/action/NavigateToPose'),
        ),
        (
            'action_clients',
            _action(type='example_interfaces/action/Fibonacci'),
            _action(type='nav2_msgs/action/NavigateToPose'),
        ),
    ],
)
def test_same_name_with_different_type_is_one_type_mismatch(section, expected, actual):
    differences = diff(
        _document(**{section: [expected]}),
        _document(**{section: [actual]}),
        node_fqn='/node',
    )

    assert _kinds(differences) == ['type_mismatch']


@pytest.mark.parametrize(
    'section,expected,actual',
    [
        ('publishers', _topic(type='std_msgs/String'), _topic(type='std_msgs/msg/String')),
        ('service_clients', _service(type='std_srvs/Trigger'), _service(type='std_srvs/srv/Trigger')),
        (
            'action_servers',
            _action(type='example_interfaces/Fibonacci'),
            _action(type='example_interfaces/action/Fibonacci'),
        ),
    ],
)
def test_short_and_fully_qualified_types_are_equal(section, expected, actual):
    assert (
        diff(
            _document(**{section: [expected]}),
            _document(**{section: [actual]}),
            node_fqn='/node',
        )
        == []
    )


@pytest.mark.parametrize(
    'node_fqn,declared_name,observed_name',
    [
        ('/robot/controller', '/status', '/status'),
        ('/node', 'status', '/status'),
        ('/robot/controller', 'status', '/robot/status'),
        ('/robot/controller', '~/status', '/robot/controller/status'),
    ],
)
def test_ros_names_resolve_against_node_identity(node_fqn, declared_name, observed_name):
    assert (
        diff(
            _document(publishers=[_topic(name=declared_name)]),
            _document(publishers=[_topic(name=observed_name)]),
            node_fqn=node_fqn,
        )
        == []
    )


@pytest.mark.parametrize(
    'section,endpoint',
    [
        ('publishers', _topic()),
        ('subscriptions', _topic()),
        ('service_servers', _service()),
        ('service_clients', _service()),
        ('action_servers', _action()),
        ('action_clients', _action()),
    ],
)
def test_endpoint_rename_reports_missing_and_extra(section, endpoint):
    actual = endpoint.copy(update={'name': '/renamed'})

    differences = diff(
        _document(**{section: [endpoint]}),
        _document(**{section: [actual]}),
        node_fqn='/node',
    )

    assert sorted(_kinds(differences)) == ['extra', 'missing']


@pytest.mark.parametrize(
    'expected_qos,actual_qos,fields',
    [
        (
            _qos(depth=10, reliability=Reliability.RELIABLE),
            _qos(depth=5, reliability=Reliability.BEST_EFFORT),
            {'depth', 'reliability'},
        ),
        (
            _qos(durability=Durability.VOLATILE, liveliness=Liveliness.AUTOMATIC),
            _qos(
                durability=Durability.TRANSIENT_LOCAL,
                liveliness=Liveliness.MANUAL_BY_TOPIC,
            ),
            {'durability', 'liveliness'},
        ),
        (
            _qos(deadline_ns=10, lifespan_ns=10),
            _qos(deadline_ns=20, lifespan_ns=20),
            {'deadline_ns', 'lifespan_ns'},
        ),
    ],
    ids=['depth-reliability', 'durability-liveliness', 'deadline-lifespan'],
)
def test_two_qos_fields_report_exactly_two_differences(expected_qos, actual_qos, fields):
    differences = diff(
        _document(publishers=[_topic(qos=expected_qos)]),
        _document(publishers=[_topic(qos=actual_qos)]),
        node_fqn='/node',
    )

    assert _kinds(differences) == ['qos_mismatch', 'qos_mismatch']
    assert {item.detail.split(':', 1)[0] for item in differences} == fields


@pytest.mark.parametrize(
    'expected,actual,expected_kinds',
    [
        (
            _document(publishers=[_topic('/qos'), _topic('/typed')]),
            _document(
                publishers=[
                    _topic('/qos', qos=_qos(durability=Durability.TRANSIENT_LOCAL)),
                    _topic('/typed', type='std_msgs/msg/Int32'),
                ]
            ),
            ['qos_mismatch', 'type_mismatch'],
        ),
        (
            _document(
                publishers=[_topic('/state')],
                parameters={'rate': ParameterDefinition(type='double')},
            ),
            _document(
                publishers=[_topic('/state', qos=_qos(durability=Durability.TRANSIENT_LOCAL))],
                parameters={'rate': ParameterDefinition(type='int')},
            ),
            ['qos_mismatch', 'type_mismatch'],
        ),
        (
            _document(
                service_servers=[_service('/reset')],
                action_clients=[_action('/navigate')],
            ),
            _document(
                service_servers=[_service('/reset', 'std_srvs/srv/SetBool')],
                action_clients=[_action('/navigate', 'nav2_msgs/action/NavigateToPose')],
            ),
            ['type_mismatch', 'type_mismatch'],
        ),
        (
            _document(
                publishers=[_topic('/state')],
                parameters={'mode': ParameterDefinition(type='string', read_only=True)},
            ),
            _document(parameters={'mode': ParameterDefinition(type='string', read_only=False)}),
            ['missing', 'property_mismatch'],
        ),
        (
            _document(parameters={'required': ParameterDefinition(type='string')}),
            _document(subscriptions=[_topic('/command')]),
            ['extra', 'missing'],
        ),
        (
            _document(action_clients=[_action('/navigate')]),
            _document(
                action_clients=[_action('/navigate', 'nav2_msgs/action/NavigateToPose')],
                parameters={'extra': ParameterDefinition(type='bool')},
            ),
            ['type_mismatch', 'extra'],
        ),
        (
            _document(
                publishers=[_topic('/state')],
                subscriptions=[_topic('/command')],
            ),
            _document(
                publishers=[_topic('/state', qos=_qos(durability=Durability.TRANSIENT_LOCAL))],
                subscriptions=[_topic('/command', qos=_qos(reliability=Reliability.BEST_EFFORT))],
            ),
            ['qos_mismatch', 'qos_mismatch'],
        ),
    ],
    ids=[
        'type-and-qos',
        'qos-and-parameter-type',
        'service-and-action-types',
        'missing-endpoint-and-parameter-property',
        'extra-endpoint-and-missing-parameter',
        'action-type-and-extra-parameter',
        'publisher-and-subscription-qos',
    ],
)
def test_two_independent_fields_report_exactly_two_differences(expected, actual, expected_kinds):
    differences = diff(expected, actual, node_fqn='/node')

    assert _kinds(differences) == expected_kinds
    assert len(differences) == 2


def test_declared_selection_policies_accept_observed_concrete_values():
    expected = _topic(
        qos=_qos(
            history=History.SYSTEM_DEFAULT,
            depth=None,
            reliability=Reliability.BEST_AVAILABLE,
            durability=Durability.SYSTEM_DEFAULT,
            liveliness=Liveliness.BEST_AVAILABLE,
        )
    )

    assert (
        diff(
            _document(publishers=[expected]),
            _document(publishers=[_topic()]),
            node_fqn='/node',
        )
        == []
    )


def test_unknown_observed_policy_cannot_prove_concrete_requirement():
    actual = _topic(qos=_qos(reliability=Reliability.SYSTEM_DEFAULT))

    differences = diff(
        _document(publishers=[_topic()]),
        _document(publishers=[actual]),
        node_fqn='/node',
    )

    assert _kinds(differences) == ['unverifiable']
    assert differences[0].detail.startswith('reliability:')


@pytest.mark.parametrize(
    'field,expected_value,actual_value',
    [
        ('history', History.KEEP_ALL, History.KEEP_LAST),
        ('reliability', Reliability.RELIABLE, Reliability.BEST_EFFORT),
        ('durability', Durability.VOLATILE, Durability.TRANSIENT_LOCAL),
        ('liveliness', Liveliness.AUTOMATIC, Liveliness.MANUAL_BY_TOPIC),
    ],
)
def test_each_concrete_qos_policy_detects_mismatch(field, expected_value, actual_value):
    expected_kwargs = {field: expected_value}
    actual_kwargs = {field: actual_value}
    if field == 'history':
        expected_kwargs['depth'] = None

    differences = diff(
        _document(publishers=[_topic(qos=_qos(**expected_kwargs))]),
        _document(publishers=[_topic(qos=_qos(**actual_kwargs))]),
        node_fqn='/node',
    )

    assert _kinds(differences) == ['qos_mismatch']
    assert differences[0].detail.startswith(f'{field}:')


def test_concrete_qos_depth_detects_mismatch():
    differences = diff(
        _document(publishers=[_topic(qos=_qos(depth=10))]),
        _document(publishers=[_topic(qos=_qos(depth=20))]),
        node_fqn='/node',
    )

    assert _kinds(differences) == ['qos_mismatch']
    assert differences[0].detail.startswith('depth:')


@pytest.mark.parametrize('section', ['publishers', 'subscriptions', 'service_servers', 'service_clients'])
def test_qos_comparison_is_routed_for_every_supported_section(section):
    endpoint = _topic if section in ('publishers', 'subscriptions') else _service
    expected = endpoint(qos=_qos(durability=Durability.VOLATILE))
    actual = endpoint(qos=_qos(durability=Durability.TRANSIENT_LOCAL))

    differences = diff(
        _document(**{section: [expected]}),
        _document(**{section: [actual]}),
        node_fqn='/node',
    )

    assert _kinds(differences) == ['qos_mismatch']


def test_omitted_optional_qos_places_no_requirement():
    expected = _topic(qos=_qos(durability=None, liveliness=None))
    actual = _topic(qos=_qos(durability=Durability.TRANSIENT_LOCAL, liveliness=Liveliness.MANUAL_BY_TOPIC))

    assert (
        diff(
            _document(publishers=[expected]),
            _document(publishers=[actual]),
            node_fqn='/node',
        )
        == []
    )


def test_zero_and_omitted_unlimited_duration_are_equal():
    expected = _topic(qos=_qos(deadline_ns=0))
    actual = _topic(qos=_qos(deadline_ns=None))

    assert (
        diff(
            _document(publishers=[expected]),
            _document(publishers=[actual]),
            node_fqn='/node',
        )
        == []
    )


def test_finite_and_unlimited_duration_are_a_mismatch():
    differences = diff(
        _document(publishers=[_topic(qos=_qos(deadline_ns=10))]),
        _document(publishers=[_topic(qos=_qos(deadline_ns=None))]),
        node_fqn='/node',
    )

    assert _kinds(differences) == ['qos_mismatch']
    assert differences[0].detail == 'deadline_ns: expected 10, got None'


@pytest.mark.parametrize('field', ['deadline_ns', 'lifespan_ns', 'liveliness_lease_duration_ns'])
def test_each_finite_qos_duration_detects_mismatch(field):
    differences = diff(
        _document(publishers=[_topic(qos=_qos(**{field: 10}))]),
        _document(publishers=[_topic(qos=_qos(**{field: 20}))]),
        node_fqn='/node',
    )

    assert _kinds(differences) == ['qos_mismatch']
    assert differences[0].detail.startswith(f'{field}:')


def test_missing_observed_depth_is_unverifiable():
    actual = _topic(qos=_qos(depth=None))

    differences = diff(
        _document(publishers=[_topic()]),
        _document(publishers=[actual]),
        node_fqn='/node',
    )

    assert _kinds(differences) == ['unverifiable']
    assert differences[0].detail.startswith('depth:')


def test_declared_service_qos_is_unverifiable_when_observation_omits_it():
    expected = _service(qos=_qos())

    differences = diff(
        _document(service_servers=[expected]),
        _document(service_servers=[_service()]),
        node_fqn='/node',
    )

    assert _kinds(differences) == ['unverifiable']


def test_observable_matching_service_qos_conforms():
    service = _service(qos=_qos())

    assert (
        diff(
            _document(service_servers=[service]),
            _document(service_servers=[service]),
            node_fqn='/node',
        )
        == []
    )


@pytest.mark.parametrize(
    'expected,actual,kind',
    [
        (
            {'declared': ParameterDefinition(type='string')},
            {},
            'missing',
        ),
        (
            {},
            {'undeclared': ParameterDefinition(type='string')},
            'extra',
        ),
        (
            {'rate': ParameterDefinition(type='double')},
            {'rate': ParameterDefinition(type='int')},
            'type_mismatch',
        ),
        (
            {'mode': ParameterDefinition(type='string', read_only=True)},
            {'mode': ParameterDefinition(type='string', read_only=False)},
            'property_mismatch',
        ),
    ],
    ids=['missing', 'extra', 'type', 'read-only'],
)
def test_each_parameter_difference_individually(expected, actual, kind):
    differences = diff(
        _document(parameters=expected),
        _document(parameters=actual),
        node_fqn='/node',
    )

    assert _kinds(differences) == [kind]


def test_parameter_rename_reports_missing_and_extra():
    differences = diff(
        _document(parameters={'old_name': ParameterDefinition(type='string')}),
        _document(parameters={'new_name': ParameterDefinition(type='string')}),
        node_fqn='/node',
    )

    assert _kinds(differences) == ['extra', 'missing']


def test_many_differences_are_all_reported():
    expected = _document(
        publishers=[_topic('/state'), _topic('/telemetry')],
        subscriptions=[_topic('/command')],
        service_servers=[_service('/reset')],
        action_clients=[_action('/navigate')],
        parameters={
            'mode': ParameterDefinition(type='string', read_only=True),
            'rate': ParameterDefinition(type='double'),
            'required': ParameterDefinition(type='bool'),
        },
    )
    actual = _document(
        publishers=[
            _topic('/status'),
            _topic('/telemetry', qos=_qos(durability=Durability.TRANSIENT_LOCAL)),
        ],
        subscriptions=[_topic('/command', type='std_msgs/msg/Int32')],
        action_clients=[_action('/navigate', 'nav2_msgs/action/NavigateToPose')],
        parameters={
            'extra': ParameterDefinition(type='bool'),
            'mode': ParameterDefinition(type='string', read_only=False),
            'rate': ParameterDefinition(type='int'),
        },
    )

    differences = diff(expected, actual, node_fqn='/node')

    assert differences == [
        Difference('missing', 'publishers', '/state', "expected type 'std_msgs/msg/String' was not observed"),
        Difference('extra', 'publishers', '/status', "observed undeclared type 'std_msgs/msg/String'"),
        Difference(
            'qos_mismatch',
            'publishers',
            '/telemetry',
            'durability: expected VOLATILE, got TRANSIENT_LOCAL',
        ),
        Difference(
            'type_mismatch',
            'subscriptions',
            '/command',
            "expected 'std_msgs/msg/String', got 'std_msgs/msg/Int32'",
        ),
        Difference(
            'missing',
            'service_servers',
            '/reset',
            "expected type 'std_srvs/srv/Trigger' was not observed",
        ),
        Difference(
            'type_mismatch',
            'action_clients',
            '/navigate',
            "expected 'example_interfaces/action/Fibonacci', got 'nav2_msgs/action/NavigateToPose'",
        ),
        Difference('extra', 'parameters', 'extra', 'observed undeclared parameter'),
        Difference('property_mismatch', 'parameters', 'mode', 'read_only: expected True, got False'),
        Difference('type_mismatch', 'parameters', 'rate', "expected 'double', got 'int'"),
        Difference('missing', 'parameters', 'required', 'declared parameter was not observed'),
    ]


def test_fixed_size_parameter_cannot_be_proven_from_runtime_base_type():
    differences = diff(
        _document(parameters={'names': ParameterDefinition(type='string_array_fixed_3')}),
        _document(parameters={'names': ParameterDefinition(type='string_array')}),
        node_fqn='/node',
    )

    assert _kinds(differences) == ['unverifiable']


def test_parameter_values_and_metadata_do_not_affect_conformance():
    expected = ParameterDefinition(
        type='double',
        default_value=1.0,
        description='declared description',
        additional_constraints='declared constraint',
    )
    actual = ParameterDefinition(
        type='double',
        default_value=9.0,
        description='observed description',
        additional_constraints='observed constraint',
    )

    assert (
        diff(
            _document(parameters={'rate': expected}),
            _document(parameters={'rate': actual}),
            node_fqn='/node',
        )
        == []
    )


def test_parameter_validation_does_not_affect_conformance():
    assert (
        diff(
            _document(parameters={'rate': ParameterDefinition(type='double', validation={'bounds': [0.0, 1.0]})}),
            _document(parameters={'rate': ParameterDefinition(type='double', validation={'bounds': [-1.0, 2.0]})}),
            node_fqn='/node',
        )
        == []
    )


def test_document_description_does_not_affect_conformance():
    assert (
        diff(
            _document(description='declared description'),
            _document(description='observed description'),
            node_fqn='/node',
        )
        == []
    )


def test_codegen_metadata_does_not_affect_conformance():
    assert (
        diff(
            _document(codegen={'cpp': {'role': 'base_class'}}),
            _document(codegen={'python': {'role': 'wrapper'}}),
            node_fqn='/node',
        )
        == []
    )


def test_exact_duplicate_endpoints_do_not_create_instance_count_differences():
    topic = _topic()

    assert (
        diff(
            _document(publishers=[topic, topic]),
            _document(publishers=[topic]),
            node_fqn='/node',
        )
        == []
    )


@pytest.mark.parametrize(
    'section,endpoint',
    [
        ('publishers', _topic()),
        ('service_servers', _service()),
        ('action_servers', _action()),
    ],
)
def test_endpoint_descriptions_do_not_affect_conformance(section, endpoint):
    expected = endpoint.copy(deep=True)
    actual = endpoint.copy(deep=True)
    expected.description = 'declared description'
    actual.description = 'observed description'

    assert (
        diff(
            _document(**{section: [expected]}),
            _document(**{section: [actual]}),
            node_fqn='/node',
        )
        == []
    )


def test_diagnostics_have_stable_section_name_kind_order():
    expected = _document(
        publishers=[_topic('/z'), _topic('/a')],
        parameters={'z': ParameterDefinition(type='string')},
    )
    actual = _document(subscriptions=[_topic('/b')])

    forward = diff(expected, actual, node_fqn='/node')
    reordered = diff(
        _document(
            publishers=[_topic('/a'), _topic('/z')],
            parameters={'z': ParameterDefinition(type='string')},
        ),
        actual,
        node_fqn='/node',
    )

    assert [str(item) for item in forward] == [str(item) for item in reordered]
    assert [(item.section, item.name) for item in forward] == [
        ('publishers', '/a'),
        ('publishers', '/z'),
        ('subscriptions', '/b'),
        ('parameters', 'z'),
    ]


def test_difference_string_is_stable_and_readable():
    difference = Difference('missing', 'publishers', '/scan', 'expected type was not observed')

    assert str(difference) == "[missing] publishers '/scan': expected type was not observed"


@pytest.mark.parametrize('node_fqn', ['node', '/', '/node/', '/node//child', ''])
def test_invalid_node_fqn_is_rejected(node_fqn):
    with pytest.raises(ValueError, match='fully qualified ROS node name'):
        diff(_document(), _document(), node_fqn=node_fqn)


def test_non_document_inputs_are_rejected():
    with pytest.raises(TypeError, match='NodlDocument'):
        diff({}, _document(), node_fqn='/node')
