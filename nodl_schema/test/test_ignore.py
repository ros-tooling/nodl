# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""ROS-free tests for ignore rules and their effect on the semantic diff."""

import pytest

from nodl_schema import IGNORE_KINDS, Difference, IgnoreRule, diff, diff_report
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

_QOS = QosProfile(
    history=History.KEEP_LAST,
    depth=10,
    reliability=Reliability.RELIABLE,
    durability=Durability.VOLATILE,
    liveliness=Liveliness.AUTOMATIC,
)


def _document(**sections):
    return NodlDocument(nodl_version=2, **sections)


def _topic(name='/topic_statistics', type='std_msgs/msg/String', qos=_QOS):
    return TopicEndpoint(name=name, type=type, qos=qos)


def test_parse_reads_kind_name_and_optional_type():
    assert IgnoreRule.parse('publisher:/topic_statistics') == IgnoreRule('publisher', '/topic_statistics')
    assert IgnoreRule.parse('publisher:/a/*:std_msgs/msg/String') == IgnoreRule(
        'publisher', '/a/*', 'std_msgs/msg/String'
    )
    assert IgnoreRule.parse('parameter:qos_overrides.*') == IgnoreRule('parameter', 'qos_overrides.*')


@pytest.mark.parametrize('kind', IGNORE_KINDS)
def test_str_round_trips_through_parse(kind):
    rule = IgnoreRule(kind, '*' if kind != 'parameter' else 'a.*')
    assert IgnoreRule.parse(str(rule)) == rule


@pytest.mark.parametrize(
    'text,message',
    [
        ('/topic_statistics', 'KIND:NAME'),
        ('publishers:/topic', 'ignore kind must be one of'),
        ('publisher:', 'must not be empty'),
        ('publisher:topic', 'fully qualified'),
        ('publisher:/topic:', 'type pattern'),
        ('parameter:limit:int', 'type pattern'),
    ],
)
def test_parse_rejects_malformed_rules(text, message):
    with pytest.raises(ValueError, match=message):
        IgnoreRule.parse(text)


def test_name_is_a_glob_over_the_full_name():
    rule = IgnoreRule('publisher', '/robot/*/stats')

    assert rule.matches('publishers', '/robot/arm/stats')
    assert rule.matches('publishers', '/robot/arm/left/stats')
    assert not rule.matches('publishers', '/robot/stats')
    assert not rule.matches('publishers', '/other/arm/stats')


def test_name_match_is_case_sensitive():
    assert not IgnoreRule('publisher', '/Stats').matches('publishers', '/stats')


def test_rule_only_matches_its_own_section():
    rule = IgnoreRule('publisher', '/topic')

    assert not rule.matches('subscriptions', '/topic')
    assert not rule.matches('parameters', '/topic')


def test_type_pattern_must_also_match():
    rule = IgnoreRule('publisher', '/topic', 'std_msgs/msg/*')

    assert rule.matches('publishers', '/topic', 'std_msgs/msg/String')
    assert not rule.matches('publishers', '/topic', 'sensor_msgs/msg/Image')
    assert not rule.matches('publishers', '/topic')


@pytest.mark.parametrize(
    'section,kind,endpoint',
    [
        ('publishers', 'publisher', _topic()),
        ('subscriptions', 'subscription', _topic()),
        ('service_servers', 'service_server', ServiceEndpoint(name='/topic_statistics', type='std_srvs/srv/Trigger')),
        ('service_clients', 'service_client', ServiceEndpoint(name='/topic_statistics', type='std_srvs/srv/Trigger')),
        (
            'action_servers',
            'action_server',
            ActionEndpoint(name='/topic_statistics', type='example_interfaces/action/Fibonacci'),
        ),
        (
            'action_clients',
            'action_client',
            ActionEndpoint(name='/topic_statistics', type='example_interfaces/action/Fibonacci'),
        ),
    ],
)
def test_each_endpoint_kind_can_be_ignored(section, kind, endpoint):
    actual = _document(**{section: [endpoint]})

    report = diff_report(_document(), actual, node_fqn='/node', ignore=[IgnoreRule(kind, '/topic_statistics')])

    assert report.differences == []
    assert [(d.kind, d.section, d.name) for d in report.ignored] == [('extra', section, '/topic_statistics')]


def test_rule_of_another_kind_does_not_ignore():
    actual = _document(publishers=[_topic()])

    differences = diff(_document(), actual, node_fqn='/node', ignore=['subscription:/topic_statistics'])

    assert [d.kind for d in differences] == ['extra']


def test_ignored_extra_is_reported_in_the_report():
    actual = _document(publishers=[_topic()])

    report = diff_report(_document(), actual, node_fqn='/node', ignore=['publisher:/topic_statistics'])

    assert report.ignored == [
        Difference('extra', 'publishers', '/topic_statistics', "observed undeclared type 'std_msgs/msg/String'")
    ]


def test_names_are_resolved_before_matching():
    actual = _document(publishers=[_topic(name='stats')])

    report = diff_report(_document(), actual, node_fqn='/robot/node', ignore=['publisher:/robot/stats'])

    assert report.differences == []
    assert len(report.ignored) == 1


def test_type_pattern_accepts_the_short_type_form():
    actual = _document(publishers=[_topic()])

    report = diff_report(_document(), actual, node_fqn='/node', ignore=['publisher:/topic_statistics:std_msgs/String'])

    assert report.differences == []


def test_type_pattern_that_does_not_match_leaves_the_extra():
    actual = _document(publishers=[_topic()])

    differences = diff(
        _document(), actual, node_fqn='/node', ignore=['publisher:/topic_statistics:sensor_msgs/msg/Image']
    )

    assert [d.kind for d in differences] == ['extra']


def test_ignore_leaves_other_extras():
    actual = _document(publishers=[_topic(), _topic(name='/other')])

    report = diff_report(_document(), actual, node_fqn='/node', ignore=['publisher:/topic_statistics'])

    assert [d.name for d in report.differences] == ['/other']
    assert [d.name for d in report.ignored] == ['/topic_statistics']


def test_ignore_does_not_hide_a_missing_declared_endpoint():
    expected = _document(publishers=[_topic()])

    report = diff_report(expected, _document(), node_fqn='/node', ignore=['publisher:/topic_statistics'])

    assert [d.kind for d in report.differences] == ['missing']
    assert report.ignored == []


def test_ignore_does_not_hide_a_qos_mismatch_on_a_declared_endpoint():
    expected = _document(publishers=[_topic()])
    actual = _document(publishers=[_topic(qos=_QOS.copy(update={'depth': 1}))])

    report = diff_report(expected, actual, node_fqn='/node', ignore=['publisher:/topic_statistics'])

    assert [d.kind for d in report.differences] == ['qos_mismatch']
    assert report.ignored == []


def test_ignored_extra_type_leaves_a_missing_instead_of_a_type_mismatch():
    expected = _document(publishers=[_topic(type='std_msgs/msg/String')])
    actual = _document(publishers=[_topic(type='std_msgs/msg/Int32')])

    report = diff_report(expected, actual, node_fqn='/node', ignore=['publisher:/topic_statistics:std_msgs/msg/Int32'])

    assert [d.kind for d in report.differences] == ['missing']
    assert [d.kind for d in report.ignored] == ['extra']


def test_ignore_selects_an_undeclared_second_type_on_a_declared_name():
    expected = _document(publishers=[_topic(type='std_msgs/msg/String')])
    actual = _document(publishers=[_topic(type='std_msgs/msg/String'), _topic(type='std_msgs/msg/Int32')])

    report = diff_report(expected, actual, node_fqn='/node', ignore=['publisher:/topic_statistics:std_msgs/msg/Int32'])

    assert report.differences == []
    assert [d.detail for d in report.ignored] == ["observed undeclared type 'std_msgs/msg/Int32'"]


def test_parameters_are_ignored_by_glob():
    actual = _document(
        parameters={
            'qos_overrides.a': ParameterDefinition(type='int'),
            'mode': ParameterDefinition(type='string'),
        }
    )

    report = diff_report(_document(), actual, node_fqn='/node', ignore=['parameter:qos_overrides.*'])

    assert [d.name for d in report.differences] == ['mode']
    assert [d.name for d in report.ignored] == ['qos_overrides.a']


def test_ignore_does_not_hide_a_missing_declared_parameter():
    expected = _document(parameters={'mode': ParameterDefinition(type='string')})

    differences = diff(expected, _document(), node_fqn='/node', ignore=['parameter:mode'])

    assert [d.kind for d in differences] == ['missing']


def test_diff_accepts_rule_objects_and_strings():
    actual = _document(publishers=[_topic(), _topic(name='/b')])

    assert diff(_document(), actual, node_fqn='/node', ignore=[IgnoreRule('publisher', '/*')]) == []
    assert diff(_document(), actual, node_fqn='/node', ignore=['publisher:/*']) == []


def test_diff_rejects_a_malformed_rule():
    with pytest.raises(ValueError, match='ignore kind'):
        diff(_document(), _document(), node_fqn='/node', ignore=['nonsense:/topic'])


def test_no_rules_matches_the_previous_behaviour():
    actual = _document(publishers=[_topic()])

    assert diff(_document(), actual, node_fqn='/node') == diff(_document(), actual, node_fqn='/node', ignore=[])
    assert diff_report(_document(), actual, node_fqn='/node').ignored == []
