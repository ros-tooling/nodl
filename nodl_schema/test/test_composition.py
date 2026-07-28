# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for NoDL document composition (the ``include`` key).

Resolution is exercised through a fake in-memory resolver so these tests need
neither an ament index nor network access. The default resolver's nodl:// URI
parsing is tested separately with a stubbed ament lookup.
"""

import pytest

from nodl_schema import load_nodl
from nodl_schema.composition import CompositionError, DefaultResolver, resolve_document

_MIN_QOS = {'history': 'SYSTEM_DEFAULT', 'reliability': 'SYSTEM_DEFAULT'}


def _pub(name, type_='std_msgs/msg/String'):
    return {'name': name, 'type': type_, 'qos': _MIN_QOS}


class FakeResolver:
    """Resolve refs from an in-memory ``{ref: yaml_text}`` mapping."""

    def __init__(self, docs: dict):
        self._docs = docs
        self.calls: list[str] = []

    def fetch(self, ref: str) -> str:
        self.calls.append(ref)
        try:
            return self._docs[ref]
        except KeyError:
            raise FileNotFoundError(ref)


# ---------------------------------------------------------------------------
# resolve_document: merging
# ---------------------------------------------------------------------------


def test_single_include_merges_entities():
    resolver = FakeResolver({
        'nodl://pkg/extra': 'nodl_version: 2\nsubscriptions:\n  - name: /extra\n    type: std_msgs/msg/String\n    qos: {history: SYSTEM_DEFAULT, reliability: SYSTEM_DEFAULT}\n',
    })
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
    resolver = FakeResolver({
        'nodl://pkg/params': 'nodl_version: 2\nparameters:\n  gain: {type: double}\n',
    })
    base = {
        'nodl_version': 2,
        'include': [{'ref': 'nodl://pkg/params'}],
        'parameters': {'rate': {'type': 'int'}},
    }
    merged = resolve_document(base, resolver)
    assert set(merged['parameters']) == {'rate', 'gain'}


def test_nested_include_is_resolved_recursively():
    resolver = FakeResolver({
        'nodl://pkg/a': 'nodl_version: 2\ninclude:\n  - ref: nodl://pkg/b\npublishers:\n  - name: /a\n    type: std_msgs/msg/String\n    qos: {history: SYSTEM_DEFAULT, reliability: SYSTEM_DEFAULT}\n',
        'nodl://pkg/b': 'nodl_version: 2\npublishers:\n  - name: /b\n    type: std_msgs/msg/String\n    qos: {history: SYSTEM_DEFAULT, reliability: SYSTEM_DEFAULT}\n',
    })
    base = {'nodl_version': 2, 'include': [{'ref': 'nodl://pkg/a'}]}
    merged = resolve_document(base, resolver)
    assert sorted(p['name'] for p in merged['publishers']) == ['/a', '/b']


def test_input_document_is_not_mutated():
    resolver = FakeResolver({
        'nodl://pkg/x': 'nodl_version: 2\npublishers:\n  - name: /x\n    type: std_msgs/msg/String\n    qos: {history: SYSTEM_DEFAULT, reliability: SYSTEM_DEFAULT}\n'
    })
    base = {'nodl_version': 2, 'include': [{'ref': 'nodl://pkg/x'}]}
    resolve_document(base, resolver)
    assert base['include'] == [{'ref': 'nodl://pkg/x'}]
    assert 'publishers' not in base


# ---------------------------------------------------------------------------
# resolve_document: collisions (error-on-collision policy)
# ---------------------------------------------------------------------------


def test_collision_between_base_and_include_errors():
    resolver = FakeResolver({
        'nodl://pkg/dup': 'nodl_version: 2\npublishers:\n  - name: /status\n    type: std_msgs/msg/String\n    qos: {history: SYSTEM_DEFAULT, reliability: SYSTEM_DEFAULT}\n'
    })
    base = {
        'nodl_version': 2,
        'include': [{'ref': 'nodl://pkg/dup'}],
        'publishers': [_pub('/status')],
    }
    with pytest.raises(CompositionError, match='/status'):
        resolve_document(base, resolver)


def test_collision_between_two_includes_errors():
    resolver = FakeResolver({
        'nodl://pkg/one': 'nodl_version: 2\npublishers:\n  - name: /shared\n    type: std_msgs/msg/String\n    qos: {history: SYSTEM_DEFAULT, reliability: SYSTEM_DEFAULT}\n',
        'nodl://pkg/two': 'nodl_version: 2\npublishers:\n  - name: /shared\n    type: std_msgs/msg/String\n    qos: {history: SYSTEM_DEFAULT, reliability: SYSTEM_DEFAULT}\n',
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
    resolver = FakeResolver({
        'nodl://pkg/sub': 'nodl_version: 2\nsubscriptions:\n  - name: /topic\n    type: std_msgs/msg/String\n    qos: {history: SYSTEM_DEFAULT, reliability: SYSTEM_DEFAULT}\n'
    })
    base = {
        'nodl_version': 2,
        'include': [{'ref': 'nodl://pkg/sub'}],
        'publishers': [_pub('/topic')],
    }
    merged = resolve_document(base, resolver)
    assert merged['publishers'][0]['name'] == '/topic'
    assert merged['subscriptions'][0]['name'] == '/topic'


# ---------------------------------------------------------------------------
# resolve_document: cycles and failures
# ---------------------------------------------------------------------------


def test_cycle_is_detected():
    resolver = FakeResolver({
        'nodl://pkg/a': 'nodl_version: 2\ninclude:\n  - ref: nodl://pkg/b\n',
        'nodl://pkg/b': 'nodl_version: 2\ninclude:\n  - ref: nodl://pkg/a\n',
    })
    base = {'nodl_version': 2, 'include': [{'ref': 'nodl://pkg/a'}]}
    with pytest.raises(CompositionError, match='cycle'):
        resolve_document(base, resolver)


def test_unresolvable_ref_raises_composition_error():
    resolver = FakeResolver({})
    base = {'nodl_version': 2, 'include': [{'ref': 'nodl://pkg/missing'}]}
    with pytest.raises(CompositionError, match='nodl://pkg/missing'):
        resolve_document(base, resolver)


def test_included_document_is_schema_validated():
    # The included document is itself invalid (bad parameter type); resolution must surface it.
    resolver = FakeResolver({'nodl://pkg/bad': 'nodl_version: 2\nparameters:\n  p: {type: not_a_type}\n'})
    base = {'nodl_version': 2, 'include': [{'ref': 'nodl://pkg/bad'}]}
    with pytest.raises(Exception):
        resolve_document(base, resolver)


# ---------------------------------------------------------------------------
# load_nodl integration
# ---------------------------------------------------------------------------


def test_load_nodl_resolves_by_default():
    resolver = FakeResolver({
        'nodl://pkg/extra': 'nodl_version: 2\nsubscriptions:\n  - name: /extra\n    type: std_msgs/msg/String\n    qos: {history: SYSTEM_DEFAULT, reliability: SYSTEM_DEFAULT}\n'
    })
    doc = load_nodl(
        'nodl_version: 2\ninclude:\n  - ref: nodl://pkg/extra\n',
        resolver=resolver,
    )
    assert doc.subscriptions[0].name == '/extra'
    assert doc.include is None


def test_load_nodl_no_resolve_keeps_include():
    resolver = FakeResolver({})
    doc = load_nodl(
        'nodl_version: 2\ninclude:\n  - ref: nodl://pkg/extra\n',
        resolve=False,
        resolver=resolver,
    )
    assert doc.include[0].ref == 'nodl://pkg/extra'
    assert resolver.calls == []


def test_load_nodl_without_include_does_not_touch_resolver():
    resolver = FakeResolver({})
    load_nodl('nodl_version: 2\n', resolver=resolver)
    assert resolver.calls == []


# ---------------------------------------------------------------------------
# DefaultResolver URI handling
# ---------------------------------------------------------------------------


def test_default_resolver_nodl_uri_uses_ament_resource(monkeypatch):
    captured = {}

    def fake_get_resource(resource_type, name):
        captured['args'] = (resource_type, name)
        return ('nodl_version: 2\n', '/some/path')

    import ament_index_python.resources as resources

    monkeypatch.setattr(resources, 'get_resource', fake_get_resource)
    text = DefaultResolver().fetch('nodl://sensor_common/imu_driver')
    assert captured['args'] == ('nodl_nodes', 'sensor_common__imu_driver')
    assert 'nodl_version' in text


def test_default_resolver_rejects_unknown_scheme():
    with pytest.raises(CompositionError, match='scheme'):
        DefaultResolver().fetch('ftp://example.com/x.yaml')
