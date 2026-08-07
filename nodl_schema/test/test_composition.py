# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for NoDL document composition (the ``include`` key).

Resolution is exercised through a fake in-memory resolver so these tests need
neither an ament index nor network access; that the protocol admits such a fake
is most of the point of having it. AmentIndexResolver's own URI handling is
tested separately with a stubbed ament lookup, and end-to-end resolution through
a real index lives in test_ament_nodl.
"""

import pytest

from nodl_schema.composition import AmentIndexResolver, CompositionError, resolve_document

_MIN_QOS = {'history': 'SYSTEM_DEFAULT', 'reliability': 'SYSTEM_DEFAULT'}
_QOS_YAML = 'qos: {history: SYSTEM_DEFAULT, reliability: SYSTEM_DEFAULT}'


def _pub(name, type_='std_msgs/msg/String'):
    return {'name': name, 'type': type_, 'qos': _MIN_QOS}


def _pub_doc(name):
    return f'nodl_version: 2\npublishers:\n  - name: {name}\n    type: std_msgs/msg/String\n    {_QOS_YAML}\n'


def _sub_doc(name):
    return f'nodl_version: 2\nsubscriptions:\n  - name: {name}\n    type: std_msgs/msg/String\n    {_QOS_YAML}\n'


class FakeResolver:
    """Resolve refs from an in-memory ``{ref: yaml_text}`` mapping."""

    def __init__(self, docs: dict):
        self._docs = docs
        self.calls: list[str] = []

    def handles(self, ref: str) -> bool:
        return ref.startswith('nodl://')

    def resolve(self, ref: str) -> str:
        self.calls.append(ref)
        try:
            return self._docs[ref]
        except KeyError:
            raise FileNotFoundError(ref)


# ---------------------------------------------------------------------------
# Merging
# ---------------------------------------------------------------------------


def test_single_include_merges_entities():
    resolver = FakeResolver({'nodl://pkg/extra': _sub_doc('/extra')})
    base = {
        'nodl_version': 2,
        'include': [{'ref': 'nodl://pkg/extra'}],
        'publishers': [_pub('/base')],
    }
    merged = resolve_document(base, resolver)
    assert 'include' not in merged
    assert [p['name'] for p in merged['publishers']] == ['/base']
    assert [s['name'] for s in merged['subscriptions']] == ['/extra']


def test_include_merges_parameters():
    resolver = FakeResolver({'nodl://pkg/params': 'nodl_version: 2\nparameters:\n  gain: {type: double}\n'})
    base = {
        'nodl_version': 2,
        'include': [{'ref': 'nodl://pkg/params'}],
        'parameters': {'rate': {'type': 'int'}},
    }
    merged = resolve_document(base, resolver)
    assert set(merged['parameters']) == {'rate', 'gain'}


def test_nested_include_is_resolved_recursively():
    resolver = FakeResolver({
        'nodl://pkg/a': (
            f'nodl_version: 2\ninclude:\n  - ref: nodl://pkg/b\n'
            f'publishers:\n  - name: /a\n    type: std_msgs/msg/String\n    {_QOS_YAML}\n'
        ),
        'nodl://pkg/b': _pub_doc('/b'),
    })
    base = {'nodl_version': 2, 'include': [{'ref': 'nodl://pkg/a'}]}
    merged = resolve_document(base, resolver)
    assert sorted(p['name'] for p in merged['publishers']) == ['/a', '/b']


def test_input_document_is_not_mutated():
    resolver = FakeResolver({'nodl://pkg/x': _pub_doc('/x')})
    base = {'nodl_version': 2, 'include': [{'ref': 'nodl://pkg/x'}]}
    resolve_document(base, resolver)
    assert base['include'] == [{'ref': 'nodl://pkg/x'}]
    assert 'publishers' not in base


def test_document_without_includes_touches_no_resolver():
    resolver = FakeResolver({})
    merged = resolve_document({'nodl_version': 2, 'publishers': [_pub('/only')]}, resolver)
    assert resolver.calls == []
    assert merged['publishers'] == [_pub('/only')]


# ---------------------------------------------------------------------------
# Collisions (error-on-collision policy)
# ---------------------------------------------------------------------------


def test_collision_between_base_and_include_errors():
    resolver = FakeResolver({'nodl://pkg/dup': _pub_doc('/status')})
    base = {
        'nodl_version': 2,
        'include': [{'ref': 'nodl://pkg/dup'}],
        'publishers': [_pub('/status')],
    }
    with pytest.raises(CompositionError, match='/status'):
        resolve_document(base, resolver)


def test_collision_between_two_includes_errors():
    resolver = FakeResolver({
        'nodl://pkg/one': _pub_doc('/shared'),
        'nodl://pkg/two': _pub_doc('/shared'),
    })
    base = {'nodl_version': 2, 'include': [{'ref': 'nodl://pkg/one'}, {'ref': 'nodl://pkg/two'}]}
    with pytest.raises(CompositionError, match='/shared'):
        resolve_document(base, resolver)


def test_parameter_collision_errors():
    resolver = FakeResolver({'nodl://pkg/p': 'nodl_version: 2\nparameters:\n  gain: {type: double}\n'})
    base = {
        'nodl_version': 2,
        'include': [{'ref': 'nodl://pkg/p'}],
        'parameters': {'gain': {'type': 'int'}},
    }
    with pytest.raises(CompositionError, match='gain'):
        resolve_document(base, resolver)


def test_same_name_different_category_is_allowed():
    # A publisher and a subscription may share a topic name; they are different categories.
    resolver = FakeResolver({'nodl://pkg/sub': _sub_doc('/topic')})
    base = {
        'nodl_version': 2,
        'include': [{'ref': 'nodl://pkg/sub'}],
        'publishers': [_pub('/topic')],
    }
    merged = resolve_document(base, resolver)
    assert merged['publishers'][0]['name'] == '/topic'
    assert merged['subscriptions'][0]['name'] == '/topic'


def test_diamond_surfaces_as_a_collision():
    # Known limitation of the strict policy: two includes pulling in the same third document is
    # a duplicate rather than a merge, because dedup across resolution paths is not performed.
    resolver = FakeResolver({
        'nodl://pkg/left': 'nodl_version: 2\ninclude:\n  - ref: nodl://pkg/shared\n',
        'nodl://pkg/right': 'nodl_version: 2\ninclude:\n  - ref: nodl://pkg/shared\n',
        'nodl://pkg/shared': _pub_doc('/shared'),
    })
    base = {'nodl_version': 2, 'include': [{'ref': 'nodl://pkg/left'}, {'ref': 'nodl://pkg/right'}]}
    with pytest.raises(CompositionError, match='/shared'):
        resolve_document(base, resolver)


# ---------------------------------------------------------------------------
# Cycles and failures
# ---------------------------------------------------------------------------


def test_cycle_is_detected():
    resolver = FakeResolver({
        'nodl://pkg/a': 'nodl_version: 2\ninclude:\n  - ref: nodl://pkg/b\n',
        'nodl://pkg/b': 'nodl_version: 2\ninclude:\n  - ref: nodl://pkg/a\n',
    })
    base = {'nodl_version': 2, 'include': [{'ref': 'nodl://pkg/a'}]}
    with pytest.raises(CompositionError, match='cycle'):
        resolve_document(base, resolver)


def test_self_reference_is_detected():
    resolver = FakeResolver({'nodl://pkg/a': 'nodl_version: 2\ninclude:\n  - ref: nodl://pkg/a\n'})
    base = {'nodl_version': 2, 'include': [{'ref': 'nodl://pkg/a'}]}
    with pytest.raises(CompositionError, match='cycle'):
        resolve_document(base, resolver)


def test_unresolvable_ref_raises_composition_error():
    resolver = FakeResolver({})
    base = {'nodl_version': 2, 'include': [{'ref': 'nodl://pkg/missing'}]}
    with pytest.raises(CompositionError, match='nodl://pkg/missing'):
        resolve_document(base, resolver)


def test_ref_no_resolver_handles_raises():
    # The schema rejects this form, so reaching resolution means it came from somewhere else;
    # this is the error a future registry would raise when no registered resolver recognizes a ref.
    resolver = FakeResolver({})
    base = {'nodl_version': 2, 'include': [{'ref': 'ftp://example.com/x.nodl.yaml'}]}
    with pytest.raises(CompositionError, match='unsupported reference'):
        resolve_document(base, resolver)
    assert resolver.calls == []


def test_included_document_is_schema_validated():
    # The included document is itself invalid (bad parameter type); resolution must surface it.
    resolver = FakeResolver({'nodl://pkg/bad': 'nodl_version: 2\nparameters:\n  p: {type: not_a_type}\n'})
    base = {'nodl_version': 2, 'include': [{'ref': 'nodl://pkg/bad'}]}
    with pytest.raises(Exception):
        resolve_document(base, resolver)


def test_included_non_mapping_raises():
    resolver = FakeResolver({'nodl://pkg/list': '- just a list\n'})
    base = {'nodl_version': 2, 'include': [{'ref': 'nodl://pkg/list'}]}
    with pytest.raises(CompositionError, match='mapping'):
        resolve_document(base, resolver)


# ---------------------------------------------------------------------------
# AmentIndexResolver
# ---------------------------------------------------------------------------


@pytest.mark.parametrize('ref', ['nodl://sensor_common/imu_driver', 'nodl://pkg/x'])
def test_ament_resolver_handles_nodl_refs(ref):
    assert AmentIndexResolver().handles(ref)


@pytest.mark.parametrize('ref', ['common/telemetry.nodl.yaml', '/abs/path.nodl.yaml', 'ftp://example.com/x.yaml', ''])
def test_ament_resolver_does_not_handle_other_forms(ref):
    assert not AmentIndexResolver().handles(ref)


def test_ament_resolver_looks_up_the_registered_resource(monkeypatch):
    captured = {}

    def fake_get_resource(resource_type, name):
        captured['args'] = (resource_type, name)
        return ('nodl_version: 2\n', '/some/prefix')

    import ament_index_python.resources as resources

    monkeypatch.setattr(resources, 'get_resource', fake_get_resource)
    text = AmentIndexResolver().resolve('nodl://sensor_common/imu_driver')
    assert captured['args'] == ('nodl_nodes', 'sensor_common__imu_driver')
    assert 'nodl_version' in text


def test_ament_resolver_missing_resource_raises(monkeypatch):
    def fake_get_resource(resource_type, name):
        raise LookupError(name)

    import ament_index_python.resources as resources

    monkeypatch.setattr(resources, 'get_resource', fake_get_resource)
    with pytest.raises(CompositionError, match='nodl://pkg/absent'):
        AmentIndexResolver().resolve('nodl://pkg/absent')


@pytest.mark.parametrize('ref', ['nodl://pkg', 'nodl://pkg/', 'nodl:///name'])
def test_ament_resolver_rejects_malformed_uri(ref):
    with pytest.raises(CompositionError, match='expected nodl://'):
        AmentIndexResolver().resolve(ref)
