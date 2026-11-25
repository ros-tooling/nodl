# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Conformance re-observes while expected endpoints are still being discovered."""

from types import SimpleNamespace

import pytest

from nodl_schema import dump_nodl
from nodl_schema.models import History, NodlDocument, ParameterDefinition, QosProfile, Reliability, TopicEndpoint
from ros2nodl import conformance
from ros2nodl.conformance import assert_conforms
from ros2nodl.describe._source import SourceError

_QOS = QosProfile(history=History.SYSTEM_DEFAULT, reliability=Reliability.SYSTEM_DEFAULT)


def _topic(name, type_name='std_msgs/msg/String'):
    return TopicEndpoint(name=name, type=type_name, qos=_QOS)


class _Graph:
    """A fake observation that returns one document per attempt on a fake clock."""

    def __init__(self, monkeypatch, documents, *, observation_sec=0.0):
        self.documents = documents
        self.observation_sec = observation_sec
        self.now = 0.0
        self.timeouts = []
        import ros2nodl.describe

        monkeypatch.setattr(ros2nodl.describe, 'describe_node', self._describe)
        monkeypatch.setattr(
            conformance,
            'time',
            SimpleNamespace(monotonic=lambda: self.now, sleep=self._sleep),
        )

    def _describe(self, node_fqn, *, timeout_sec, options):
        del node_fqn, options
        self.timeouts.append(timeout_sec)
        self.now += self.observation_sec
        document = self.documents[min(len(self.timeouts), len(self.documents)) - 1]
        if isinstance(document, Exception):
            raise document
        return SimpleNamespace(doc=document, gaps=[])

    def _sleep(self, seconds):
        self.now += seconds

    @property
    def attempts(self):
        return len(self.timeouts)


@pytest.fixture
def spec(tmp_path):
    path = tmp_path / 'node.nodl.yaml'
    path.write_text(dump_nodl(NodlDocument(publishers=[_topic('/state')]), format='yaml'))
    return str(path)


def _conforms(spec, **kwargs):
    return assert_conforms(nodl_file=spec, node_fqn='/fixture', **kwargs)


def test_a_missing_endpoint_that_appears_conforms_on_the_second_attempt(monkeypatch, spec):
    graph = _Graph(monkeypatch, [NodlDocument(), NodlDocument(publishers=[_topic('/state')])])

    _conforms(spec, timeout_sec=5.0)

    assert graph.attempts == 2
    assert graph.timeouts[0] == 5.0
    assert graph.timeouts[1] < 5.0


def test_a_conforming_node_is_observed_once_without_delay(monkeypatch, spec):
    graph = _Graph(monkeypatch, [NodlDocument(publishers=[_topic('/state')])])

    _conforms(spec)

    assert graph.attempts == 1
    assert graph.now == 0.0


def test_a_node_that_never_conforms_fails_with_the_last_report_within_the_timeout(monkeypatch, spec):
    graph = _Graph(monkeypatch, [NodlDocument()], observation_sec=0.1)

    with pytest.raises(AssertionError) as error:
        _conforms(spec, timeout_sec=6.0)

    assert str(error.value) == (
        "NoDL conformance failed for '/fixture':\n"
        "  [missing] publishers '/state': expected type 'std_msgs/msg/String' was not observed"
    )
    assert graph.attempts > 2
    assert graph.now <= 6.0
    assert all(timeout <= 6.0 for timeout in graph.timeouts)
    assert all(timeout >= conformance._MIN_ATTEMPT_SEC for timeout in graph.timeouts)


def test_an_observation_that_uses_the_whole_timeout_is_not_followed_by_another(monkeypatch, spec):
    graph = _Graph(monkeypatch, [NodlDocument()], observation_sec=5.0)

    with pytest.raises(AssertionError):
        _conforms(spec, timeout_sec=5.0)

    assert graph.attempts == 1
    assert graph.now == 5.0


def test_no_observation_starts_with_less_than_the_minimum_time_left(monkeypatch, spec):
    graph = _Graph(monkeypatch, [NodlDocument(), NodlDocument(publishers=[_topic('/state')])], observation_sec=3.0)

    with pytest.raises(AssertionError) as error:
        _conforms(spec, timeout_sec=5.0)

    assert graph.attempts == 1
    assert "[missing] publishers '/state'" in str(error.value)


def test_a_failed_later_observation_returns_the_previous_report(monkeypatch, spec):
    graph = _Graph(monkeypatch, [NodlDocument(), SourceError('did not appear in the graph')])

    with pytest.raises(AssertionError, match=r"\[missing\] publishers '/state'"):
        _conforms(spec, timeout_sec=5.0)

    assert graph.attempts == 2


def test_a_failed_first_observation_propagates(monkeypatch, spec):
    _Graph(monkeypatch, [SourceError('did not appear in the graph')])

    with pytest.raises(SourceError):
        _conforms(spec)


@pytest.mark.parametrize(
    'observed',
    [
        NodlDocument(publishers=[_topic('/state'), _topic('/extra')]),
        NodlDocument(publishers=[_topic('/state', 'std_msgs/msg/Int32')]),
    ],
    ids=['extra', 'type_mismatch'],
)
def test_other_differences_fail_without_a_retry(monkeypatch, spec, observed):
    graph = _Graph(monkeypatch, [observed])

    with pytest.raises(AssertionError):
        _conforms(spec)

    assert graph.attempts == 1


def test_a_missing_endpoint_with_another_difference_fails_without_a_retry(monkeypatch, spec):
    graph = _Graph(monkeypatch, [NodlDocument(publishers=[_topic('/extra')])])

    with pytest.raises(AssertionError):
        _conforms(spec)

    assert graph.attempts == 1


def test_a_missing_parameter_fails_without_a_retry(monkeypatch, tmp_path):
    path = tmp_path / 'node.nodl.yaml'
    path.write_text(dump_nodl(NodlDocument(parameters={'mode': ParameterDefinition(type='string')}), format='yaml'))
    graph = _Graph(monkeypatch, [NodlDocument()])

    with pytest.raises(AssertionError):
        _conforms(str(path))

    assert graph.attempts == 1


def test_ignored_extras_do_not_stop_a_retry_for_a_transient_missing_endpoint(monkeypatch, spec):
    graph = _Graph(
        monkeypatch,
        [
            NodlDocument(publishers=[_topic('/topic_statistics')]),
            NodlDocument(publishers=[_topic('/topic_statistics'), _topic('/state')]),
        ],
    )

    report = _conforms(spec, ignore=['publisher:/topic_statistics'])

    assert graph.attempts == 2
    assert [d.name for d in report.ignored] == ['/topic_statistics']
