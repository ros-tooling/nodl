"""Unit tests for nodl_test._compare — no rclpy or live nodes required."""
import pytest

from nodl.models import NodlDocument, NodeMetadata, Parameter, QoS, ServiceEndpoint, TopicEndpoint
from nodl_test._compare import (
    Difference,
    _compare_parameters,
    _compare_services,
    _compare_topics,
    _qos_matches,
    compare,
)

# ---------------------------------------------------------------------------
# _expand_tilde (imported from nodl.resolve, tested indirectly via _compare_*)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# _qos_matches
# ---------------------------------------------------------------------------

def test_qos_matches_both_none():
    ok, reason = _qos_matches(None, None)
    assert ok
    assert reason == ''


def test_qos_matches_expected_none_actual_concrete():
    # expected not specified → skip comparison → ok
    ok, _ = _qos_matches(None, QoS(history=10, reliability='RELIABLE'))
    assert ok


def test_qos_matches_actual_none_expected_concrete():
    # actual indeterminate (SYSTEM_DEFAULT) → wildcard → ok
    ok, _ = _qos_matches(QoS(history=10, reliability='RELIABLE'), None)
    assert ok


def test_qos_matches_identical():
    q = QoS(history=10, reliability='RELIABLE')
    ok, _ = _qos_matches(q, q)
    assert ok


def test_qos_matches_reliability_mismatch():
    ok, reason = _qos_matches(
        QoS(history=10, reliability='RELIABLE'),
        QoS(history=10, reliability='BEST_EFFORT'),
    )
    assert not ok
    assert 'reliability' in reason


def test_qos_matches_history_mismatch():
    ok, reason = _qos_matches(
        QoS(history=10, reliability='RELIABLE'),
        QoS(history=5, reliability='RELIABLE'),
    )
    assert not ok
    assert 'history' in reason


def test_qos_matches_keep_all():
    ok, _ = _qos_matches(
        QoS(history='ALL', reliability='RELIABLE'),
        QoS(history='ALL', reliability='RELIABLE'),
    )
    assert ok


def test_qos_matches_durability_mismatch():
    ok, reason = _qos_matches(
        QoS(history=10, reliability='RELIABLE', durability='TRANSIENT_LOCAL'),
        QoS(history=10, reliability='RELIABLE', durability='VOLATILE'),
    )
    assert not ok
    assert 'durability' in reason


def test_qos_matches_durability_none_in_actual():
    # actual.durability is None → field not compared
    ok, _ = _qos_matches(
        QoS(history=10, reliability='RELIABLE', durability='TRANSIENT_LOCAL'),
        QoS(history=10, reliability='RELIABLE'),
    )
    assert ok


# ---------------------------------------------------------------------------
# _compare_topics
# ---------------------------------------------------------------------------

_STD_PUB = TopicEndpoint(topic='/out', type='std_msgs/msg/String')


def test_topics_match_identical():
    diffs = _compare_topics([_STD_PUB], [_STD_PUB], 'publisher')
    assert diffs == []


def test_topics_missing_in_actual():
    diffs = _compare_topics([_STD_PUB], [], 'publisher')
    assert len(diffs) == 1
    assert diffs[0].kind == 'missing'
    assert diffs[0].name == '/out'


def test_topics_extra_in_actual():
    diffs = _compare_topics([], [_STD_PUB], 'publisher')
    assert len(diffs) == 1
    assert diffs[0].kind == 'extra'


def test_topics_type_mismatch():
    expected = TopicEndpoint(topic='/out', type='std_msgs/msg/String')
    actual = TopicEndpoint(topic='/out', type='std_msgs/msg/Int32')
    diffs = _compare_topics([expected], [actual], 'publisher')
    assert len(diffs) == 1
    assert diffs[0].kind == 'type_mismatch'
    assert 'std_msgs/msg/Int32' in diffs[0].detail


def test_topics_qos_mismatch():
    expected = TopicEndpoint(
        topic='/out', type='std_msgs/msg/String',
        qos=QoS(history=10, reliability='RELIABLE'),
    )
    actual = TopicEndpoint(
        topic='/out', type='std_msgs/msg/String',
        qos=QoS(history=10, reliability='BEST_EFFORT'),
    )
    diffs = _compare_topics([expected], [actual], 'publisher')
    assert len(diffs) == 1
    assert diffs[0].kind == 'qos_mismatch'


def test_topics_qos_skip_when_expected_none():
    expected = TopicEndpoint(topic='/out', type='std_msgs/msg/String')  # no qos
    actual = TopicEndpoint(
        topic='/out', type='std_msgs/msg/String',
        qos=QoS(history=10, reliability='BEST_EFFORT'),
    )
    diffs = _compare_topics([expected], [actual], 'publisher')
    assert diffs == []


def test_topics_qos_pass_when_actual_none():
    expected = TopicEndpoint(
        topic='/out', type='std_msgs/msg/String',
        qos=QoS(history=10, reliability='RELIABLE'),
    )
    actual = TopicEndpoint(topic='/out', type='std_msgs/msg/String')  # no qos = wildcarded
    diffs = _compare_topics([expected], [actual], 'publisher')
    assert diffs == []


def test_topics_section_label_in_difference():
    diffs = _compare_topics([_STD_PUB], [], 'subscription')
    assert diffs[0].section == 'subscription'


# ---------------------------------------------------------------------------
# _compare_services
# ---------------------------------------------------------------------------

_RESET_SRV = ServiceEndpoint(name='/reset', type='std_srvs/srv/Trigger')


def test_services_match_identical():
    diffs = _compare_services([_RESET_SRV], [_RESET_SRV], 'service_server')
    assert diffs == []


def test_services_missing():
    diffs = _compare_services([_RESET_SRV], [], 'service_server')
    assert len(diffs) == 1
    assert diffs[0].kind == 'missing'


def test_services_extra():
    diffs = _compare_services([], [_RESET_SRV], 'service_server')
    assert len(diffs) == 1
    assert diffs[0].kind == 'extra'


def test_services_type_mismatch():
    expected = ServiceEndpoint(name='/reset', type='std_srvs/srv/Trigger')
    actual = ServiceEndpoint(name='/reset', type='std_srvs/srv/SetBool')
    diffs = _compare_services([expected], [actual], 'service_server')
    assert len(diffs) == 1
    assert diffs[0].kind == 'type_mismatch'


# ---------------------------------------------------------------------------
# _compare_parameters
# ---------------------------------------------------------------------------

_PARAMS_EXPECTED = {
    'rate': Parameter(type='double', default_value=10.0),
    'label': Parameter(type='string'),
}
_PARAMS_ACTUAL = {
    'rate': Parameter(type='double'),
    'label': Parameter(type='string'),
}


def test_parameters_match():
    diffs = _compare_parameters(_PARAMS_EXPECTED, _PARAMS_ACTUAL)
    assert diffs == []


def test_parameters_missing():
    diffs = _compare_parameters(_PARAMS_EXPECTED, {'rate': Parameter(type='double')})
    assert len(diffs) == 1
    assert diffs[0].kind == 'missing'
    assert diffs[0].name == 'label'


def test_parameters_extra():
    extra = dict(_PARAMS_ACTUAL)
    extra['unexpected'] = Parameter(type='bool')
    diffs = _compare_parameters(_PARAMS_EXPECTED, extra)
    assert len(diffs) == 1
    assert diffs[0].kind == 'extra'
    assert diffs[0].name == 'unexpected'


def test_parameters_type_mismatch():
    diffs = _compare_parameters(
        {'rate': Parameter(type='double')},
        {'rate': Parameter(type='int')},
    )
    assert len(diffs) == 1
    assert diffs[0].kind == 'type_mismatch'
    assert "'int'" in diffs[0].detail


# ---------------------------------------------------------------------------
# compare (top-level)
# ---------------------------------------------------------------------------

def test_compare_empty_documents():
    diffs = compare(NodlDocument(), NodlDocument())
    assert diffs == []


def test_compare_matching_documents():
    doc = NodlDocument(
        node=NodeMetadata(name='n'),
        publishers=[TopicEndpoint(topic='/a', type='std_msgs/msg/String')],
        parameters={'x': Parameter(type='double')},
    )
    diffs = compare(doc, doc)
    assert diffs == []


def test_compare_detects_missing_publisher():
    expected = NodlDocument(
        publishers=[TopicEndpoint(topic='/a', type='std_msgs/msg/String')],
    )
    actual = NodlDocument()
    diffs = compare(expected, actual)
    assert any(d.kind == 'missing' and d.section == 'publisher' for d in diffs)


def test_compare_detects_extra_subscription():
    expected = NodlDocument()
    actual = NodlDocument(
        subscriptions=[TopicEndpoint(topic='/extra', type='std_msgs/msg/String')],
    )
    diffs = compare(expected, actual)
    assert any(d.kind == 'extra' and d.section == 'subscription' for d in diffs)


def test_difference_str_format():
    d = Difference(kind='missing', section='publisher', name='/scan', detail='not found')
    s = str(d)
    assert '[missing]' in s
    assert 'publisher' in s
    assert '/scan' in s


# ---------------------------------------------------------------------------
# node_fqn / tilde expansion
# ---------------------------------------------------------------------------

def test_topics_tilde_expansion_matches():
    expected = [TopicEndpoint(topic='~/out', type='std_msgs/msg/String')]
    actual = [TopicEndpoint(topic='/ns/node/out', type='std_msgs/msg/String')]
    diffs = _compare_topics(expected, actual, 'publisher', node_fqn='/ns/node')
    assert diffs == []


def test_topics_tilde_expansion_no_fqn_stays_literal():
    # Without a node_fqn, '~/out' is not expanded so it fails to match '/ns/node/out'.
    expected = [TopicEndpoint(topic='~/out', type='std_msgs/msg/String')]
    actual = [TopicEndpoint(topic='/ns/node/out', type='std_msgs/msg/String')]
    diffs = _compare_topics(expected, actual, 'publisher', node_fqn=None)
    assert any(d.kind == 'missing' and d.name == '~/out' for d in diffs)


def test_services_tilde_expansion_matches():
    expected = [ServiceEndpoint(name='~/change_state', type='lifecycle_msgs/srv/ChangeState')]
    actual = [ServiceEndpoint(name='/my_node/change_state', type='lifecycle_msgs/srv/ChangeState')]
    diffs = _compare_services(expected, actual, 'service_server', node_fqn='/my_node')
    assert diffs == []


def test_compare_passes_node_fqn_through():
    expected = NodlDocument(
        service_servers=[ServiceEndpoint(name='~/get_state', type='lifecycle_msgs/srv/GetState')],
    )
    actual = NodlDocument(
        service_servers=[ServiceEndpoint(name='/my_ns/my_node/get_state', type='lifecycle_msgs/srv/GetState')],
    )
    diffs = compare(expected, actual, node_fqn='/my_ns/my_node')
    assert diffs == []
