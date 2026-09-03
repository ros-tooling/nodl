# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0

from pathlib import Path
from types import SimpleNamespace

import pytest

from nodl_schema import Difference, Resolver, dump_nodl, resolver_registered
from nodl_schema.models import (
    History,
    NodlDocument,
    QosProfile,
    Reference,
    Reliability,
    TopicEndpoint,
)
from ros2nodl import conformance
from ros2nodl.conformance import assert_conforms, check_conformance

FIXTURES = Path(__file__).parent / 'fixtures'


class _Resolver(Resolver):
    scheme = 'test://'

    def __init__(self, documents):
        self.documents = documents

    def handles(self, ref):
        return ref.startswith(self.scheme)

    def resolve(self, ref, origin=None):
        del origin
        return self.documents[ref]


def _topic(name):
    return TopicEndpoint(
        name=name,
        type='std_msgs/msg/String',
        qos=QosProfile(
            history=History.SYSTEM_DEFAULT,
            reliability=Reliability.SYSTEM_DEFAULT,
        ),
    )


def _minimal_document():
    return NodlDocument()


def _describe_result(*, gaps=None):
    return SimpleNamespace(doc=_minimal_document(), gaps=gaps or [])


def _patch_describe(monkeypatch, result):
    import ros2nodl.describe

    monkeypatch.setattr(ros2nodl.describe, 'describe_node', lambda *args, **kwargs: result)


def _track_describe_calls(monkeypatch):
    calls = []

    def describe_node(*args, **kwargs):
        calls.append((args, kwargs))

    import ros2nodl.describe

    monkeypatch.setattr(ros2nodl.describe, 'describe_node', describe_node)
    return calls


@pytest.mark.parametrize('filename', ['minimal.nodl.yaml', 'minimal.nodl.json'])
def test_check_conformance_loads_explicit_yaml_and_json(monkeypatch, filename):
    _patch_describe(monkeypatch, _describe_result())

    assert (
        check_conformance(
            nodl_file=str(FIXTURES / filename),
            node_fqn='/fixture',
        )
        == []
    )


def test_check_conformance_uses_public_describe_path_once(monkeypatch):
    calls = []

    def describe_node(*args, **kwargs):
        calls.append((args, kwargs))
        return _describe_result()

    import ros2nodl.describe

    monkeypatch.setattr(ros2nodl.describe, 'describe_node', describe_node)

    assert (
        check_conformance(
            nodl_file=str(FIXTURES / 'minimal.nodl.yaml'),
            node_fqn='/robot/fixture',
            timeout_sec=3.0,
        )
        == []
    )

    assert len(calls) == 1
    args, kwargs = calls[0]
    assert args == ('/robot/fixture',)
    assert kwargs['timeout_sec'] == 3.0
    assert kwargs['options'].include_parameters is True
    assert kwargs['options'].keep_hidden is False


def test_check_conformance_rejects_missing_file_before_describe(monkeypatch, tmp_path):
    calls = _track_describe_calls(monkeypatch)
    missing = tmp_path / 'missing.nodl.yaml'

    with pytest.raises(ValueError, match=str(missing)):
        check_conformance(nodl_file=str(missing), node_fqn='/fixture')

    assert calls == []


def test_check_conformance_compares_resolved_includes(monkeypatch, tmp_path):
    included = NodlDocument(publishers=[_topic('/state')])
    included_path = tmp_path / 'common.nodl.yaml'
    included_path.write_text(dump_nodl(included), encoding='utf-8')
    root = tmp_path / 'composed.nodl.yaml'
    root.write_text(
        dump_nodl(NodlDocument(include=[Reference(ref='test://common')])),
        encoding='utf-8',
    )
    observed = _minimal_document()
    _patch_describe(monkeypatch, SimpleNamespace(doc=observed, gaps=[]))
    calls = []
    monkeypatch.setattr(
        conformance,
        'diff',
        lambda expected, actual, *, node_fqn: calls.append((expected, actual, node_fqn)) or [],
    )

    with resolver_registered(_Resolver({'test://common': included_path})):
        assert check_conformance(nodl_file=str(root), node_fqn='/fixture') == []

    expected, actual, node_fqn = calls[0]
    assert expected.include is None
    assert [publisher.name for publisher in expected.publishers] == ['/state']
    assert actual is observed
    assert node_fqn == '/fixture'


def test_check_conformance_rejects_unresolved_include_before_describe(monkeypatch, tmp_path):
    calls = _track_describe_calls(monkeypatch)
    root = tmp_path / 'composed.nodl.yaml'
    root.write_text(
        dump_nodl(NodlDocument(include=[Reference(ref='test://missing')])),
        encoding='utf-8',
    )

    with resolver_registered(_Resolver({})), pytest.raises(ValueError, match='test://missing'):
        check_conformance(nodl_file=str(root), node_fqn='/fixture')

    assert calls == []


def test_check_conformance_rejects_include_collision_before_describe(monkeypatch, tmp_path):
    calls = _track_describe_calls(monkeypatch)
    duplicate = NodlDocument(publishers=[_topic('/state')])
    duplicate_path = tmp_path / 'duplicate.nodl.yaml'
    duplicate_path.write_text(dump_nodl(duplicate), encoding='utf-8')
    root = tmp_path / 'composed.nodl.yaml'
    root.write_text(
        dump_nodl(
            NodlDocument(
                publishers=[_topic('/state')],
                include=[Reference(ref='test://duplicate')],
            )
        ),
        encoding='utf-8',
    )

    resolver = _Resolver({'test://duplicate': duplicate_path})
    with resolver_registered(resolver), pytest.raises(ValueError, match='/state'):
        check_conformance(nodl_file=str(root), node_fqn='/fixture')

    assert calls == []


@pytest.mark.parametrize(
    'text',
    [
        'nodl_version: [',
        '{"nodl_version":',
        'nodl_version: 1',
    ],
)
def test_check_conformance_rejects_invalid_documents(tmp_path, text):
    invalid = tmp_path / 'invalid.nodl.yaml'
    invalid.write_text(text, encoding='utf-8')

    with pytest.raises(ValueError, match='failed to load NoDL document'):
        check_conformance(nodl_file=str(invalid), node_fqn='/fixture')


def test_check_conformance_propagates_describe_failure_without_diff(monkeypatch):
    import ros2nodl.describe

    def describe_node(*args, **kwargs):
        raise RuntimeError('observation failed')

    monkeypatch.setattr(ros2nodl.describe, 'describe_node', describe_node)
    monkeypatch.setattr(conformance, 'diff', lambda *args, **kwargs: pytest.fail('diff called'))

    with pytest.raises(RuntimeError, match='observation failed'):
        check_conformance(
            nodl_file=str(FIXTURES / 'minimal.nodl.yaml'),
            node_fqn='/fixture',
        )


def test_check_conformance_converts_gaps_and_passes_only_documents_to_diff(monkeypatch):
    from ros2nodl.describe import Gap

    result = _describe_result(
        gaps=[
            Gap(path='publishers./state.qos', reason='QoS is unknown'),
            Gap(path='parameters.mode.type', reason='type is unsupported'),
        ]
    )
    _patch_describe(monkeypatch, result)
    calls = []
    comparison = Difference('extra', 'publishers', '/extra', 'observed undeclared type')

    def compare(expected, actual, *, node_fqn):
        calls.append((expected, actual, node_fqn))
        return [comparison]

    monkeypatch.setattr(conformance, 'diff', compare)

    differences = check_conformance(
        nodl_file=str(FIXTURES / 'minimal.nodl.yaml'),
        node_fqn='/fixture',
        timeout_sec=3.0,
    )

    assert calls[0][1] is result.doc
    assert calls[0][2] == '/fixture'
    assert {(difference.section, difference.name) for difference in differences} == {
        ('parameters', 'parameters.mode.type'),
        ('publishers', '/extra'),
        ('publishers', 'publishers./state.qos'),
    }
    assert any('QoS is unknown' in str(difference) for difference in differences)


def test_assert_conforms_aggregates_all_differences(monkeypatch):
    differences = [
        Difference('missing', 'publishers', '/state', 'not observed'),
        Difference('extra', 'subscriptions', '/command', 'not declared'),
    ]
    monkeypatch.setattr(conformance, 'check_conformance', lambda **kwargs: differences)

    with pytest.raises(AssertionError) as error:
        assert_conforms(nodl_file='node.nodl.yaml', node_fqn='/fixture')

    assert str(differences[0]) in str(error.value)
    assert str(differences[1]) in str(error.value)
