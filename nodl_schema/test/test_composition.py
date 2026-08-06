# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for NoDL document composition (the ``include`` key).

Resolution is exercised through a fake in-memory resolver so these tests need
neither an ament index nor network access. The default resolver's nodl:// URI
parsing is tested separately with a stubbed ament lookup.
"""

from pathlib import Path

import pytest

from nodl_schema import load_nodl
from nodl_schema.composition import (
    CompositionError,
    DefaultResolver,
    local_references,
    path_to_ref,
    resolve_document,
    rewrite_references,
)

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


def test_default_resolver_reads_file_ref(tmp_path: Path):
    doc = tmp_path / 'x.nodl.yaml'
    doc.write_text('nodl_version: 2\n')
    assert 'nodl_version' in DefaultResolver().fetch(path_to_ref(doc))


def test_default_resolver_missing_file_raises():
    with pytest.raises(CompositionError):
        DefaultResolver().fetch(path_to_ref('/nonexistent/nowhere.nodl.yaml'))


# ---------------------------------------------------------------------------
# Relative references: resolved against the origin of the containing document
# ---------------------------------------------------------------------------


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def test_relative_ref_resolves_against_document_directory(tmp_path: Path):
    _write(tmp_path / 'common' / 'telemetry.nodl.yaml', f'nodl_version: 2\npublishers:\n  - {_pub("/telem")}\n')
    main = _write(
        tmp_path / 'my_node.nodl.yaml',
        'nodl_version: 2\ninclude:\n  - ref: common/telemetry.nodl.yaml\n',
    )
    doc = load_nodl(main.read_text(), base=main)
    assert [p.name for p in doc.publishers] == ['/telem']


def test_relative_ref_resolves_from_open_file_without_explicit_base(tmp_path: Path):
    # An open file knows its own path, so the CLI does not have to pass it twice.
    _write(tmp_path / 'shared.nodl.yaml', f'nodl_version: 2\npublishers:\n  - {_pub("/shared")}\n')
    main = _write(tmp_path / 'main.nodl.yaml', 'nodl_version: 2\ninclude:\n  - ref: shared.nodl.yaml\n')
    with main.open() as f:
        doc = load_nodl(f)
    assert [p.name for p in doc.publishers] == ['/shared']


def test_relative_ref_is_relative_to_the_including_document_not_the_root(tmp_path: Path):
    # b/ leaf.nodl.yaml is named relative to b/mid.nodl.yaml, not to the top-level document.
    _write(tmp_path / 'b' / 'leaf.nodl.yaml', f'nodl_version: 2\npublishers:\n  - {_pub("/leaf")}\n')
    _write(tmp_path / 'b' / 'mid.nodl.yaml', 'nodl_version: 2\ninclude:\n  - ref: leaf.nodl.yaml\n')
    main = _write(tmp_path / 'top.nodl.yaml', 'nodl_version: 2\ninclude:\n  - ref: b/mid.nodl.yaml\n')
    doc = load_nodl(main.read_text(), base=main)
    assert [p.name for p in doc.publishers] == ['/leaf']


def test_relative_ref_may_walk_upward(tmp_path: Path):
    _write(tmp_path / 'shared' / 'base.nodl.yaml', f'nodl_version: 2\npublishers:\n  - {_pub("/base")}\n')
    main = _write(
        tmp_path / 'nodl' / 'node.nodl.yaml',
        'nodl_version: 2\ninclude:\n  - ref: ../shared/base.nodl.yaml\n',
    )
    doc = load_nodl(main.read_text(), base=main)
    assert [p.name for p in doc.publishers] == ['/base']


def test_relative_ref_without_base_raises(tmp_path: Path):
    with pytest.raises(CompositionError, match='nothing to resolve against'):
        load_nodl('nodl_version: 2\ninclude:\n  - ref: common/telemetry.nodl.yaml\n')


def test_relative_ref_inside_ament_document_raises():
    # A document fetched from the index is text with no location, so nothing in it can be relative.
    resolver = FakeResolver({
        'nodl://pkg/a': 'nodl_version: 2\ninclude:\n  - ref: sibling.nodl.yaml\n',
    })
    base = {'nodl_version': 2, 'include': [{'ref': 'nodl://pkg/a'}]}
    with pytest.raises(CompositionError, match='no location to be relative to'):
        resolve_document(base, resolver)


def test_relative_cycle_is_detected_across_spellings(tmp_path: Path):
    # a -> b -> ./a, two spellings of the same file. Normalizing before the cycle check is what
    # makes this terminate rather than recursing.
    _write(tmp_path / 'a.nodl.yaml', 'nodl_version: 2\ninclude:\n  - ref: b.nodl.yaml\n')
    _write(tmp_path / 'b.nodl.yaml', 'nodl_version: 2\ninclude:\n  - ref: ./a.nodl.yaml\n')
    main = tmp_path / 'a.nodl.yaml'
    with pytest.raises(CompositionError, match='cycle'):
        load_nodl(main.read_text(), base=main)


def test_missing_relative_ref_raises(tmp_path: Path):
    main = _write(tmp_path / 'main.nodl.yaml', 'nodl_version: 2\ninclude:\n  - ref: nope.nodl.yaml\n')
    with pytest.raises(CompositionError, match='nope.nodl.yaml'):
        load_nodl(main.read_text(), base=main)


# ---------------------------------------------------------------------------
# local_references: what registration needs to know about
# ---------------------------------------------------------------------------


def test_local_references_is_transitive(tmp_path: Path):
    leaf = _write(tmp_path / 'leaf.nodl.yaml', 'nodl_version: 2\n')
    mid = _write(tmp_path / 'mid.nodl.yaml', 'nodl_version: 2\ninclude:\n  - ref: leaf.nodl.yaml\n')
    main = _write(tmp_path / 'main.nodl.yaml', 'nodl_version: 2\ninclude:\n  - ref: mid.nodl.yaml\n')
    found = local_references({'include': [{'ref': 'mid.nodl.yaml'}]}, path_to_ref(main))
    assert found == [mid, leaf]


def test_local_references_ignores_nodl_uris(tmp_path: Path):
    main = _write(tmp_path / 'main.nodl.yaml', 'nodl_version: 2\n')
    data = {'include': [{'ref': 'nodl://other_pkg/thing'}]}
    assert local_references(data, path_to_ref(main)) == []


def test_local_references_survives_a_cycle(tmp_path: Path):
    a = _write(tmp_path / 'a.nodl.yaml', 'nodl_version: 2\ninclude:\n  - ref: b.nodl.yaml\n')
    b = _write(tmp_path / 'b.nodl.yaml', 'nodl_version: 2\ninclude:\n  - ref: a.nodl.yaml\n')
    found = local_references({'include': [{'ref': 'b.nodl.yaml'}]}, path_to_ref(a))
    assert found == [b, a]


def test_local_references_deduplicates(tmp_path: Path):
    shared = _write(tmp_path / 'shared.nodl.yaml', 'nodl_version: 2\n')
    main = _write(tmp_path / 'main.nodl.yaml', 'nodl_version: 2\n')
    data = {'include': [{'ref': 'shared.nodl.yaml'}, {'ref': './shared.nodl.yaml'}]}
    assert local_references(data, path_to_ref(main)) == [shared]


# ---------------------------------------------------------------------------
# rewrite_references: what registration installs
# ---------------------------------------------------------------------------


def test_rewrite_replaces_relative_ref_with_registered_name(tmp_path: Path):
    shared = _write(tmp_path / 'common' / 'telemetry.nodl.yaml', 'nodl_version: 2\n')
    main = tmp_path / 'my_node.nodl.yaml'
    data = {'nodl_version': 2, 'include': [{'ref': 'common/telemetry.nodl.yaml'}]}
    out = rewrite_references(data, {shared: 'my_pkg/telemetry'}, path_to_ref(main))
    assert out['include'] == [{'ref': 'nodl://my_pkg/telemetry'}]


def test_rewrite_leaves_nodl_uris_alone(tmp_path: Path):
    main = tmp_path / 'my_node.nodl.yaml'
    data = {'nodl_version': 2, 'include': [{'ref': 'nodl://other_pkg/thing'}]}
    out = rewrite_references(data, {}, path_to_ref(main))
    assert out['include'] == [{'ref': 'nodl://other_pkg/thing'}]


def test_rewrite_changes_nothing_else(tmp_path: Path):
    shared = _write(tmp_path / 'shared.nodl.yaml', 'nodl_version: 2\n')
    main = tmp_path / 'my_node.nodl.yaml'
    data = {
        'nodl_version': 2,
        'description': 'a node',
        'include': [{'ref': 'shared.nodl.yaml'}],
        'publishers': [_pub('/status')],
    }
    out = rewrite_references(data, {shared: 'my_pkg/shared'}, path_to_ref(main))
    assert out['description'] == 'a node'
    assert out['publishers'] == [_pub('/status')]
    # Entities are not merged in; only the reference changed.
    assert 'subscriptions' not in out


def test_rewrite_does_not_mutate_input(tmp_path: Path):
    shared = _write(tmp_path / 'shared.nodl.yaml', 'nodl_version: 2\n')
    main = tmp_path / 'my_node.nodl.yaml'
    data = {'nodl_version': 2, 'include': [{'ref': 'shared.nodl.yaml'}]}
    rewrite_references(data, {shared: 'my_pkg/shared'}, path_to_ref(main))
    assert data['include'] == [{'ref': 'shared.nodl.yaml'}]


def test_rewrite_of_unregistered_reference_raises(tmp_path: Path):
    main = tmp_path / 'my_node.nodl.yaml'
    data = {'nodl_version': 2, 'include': [{'ref': 'shared.nodl.yaml'}]}
    with pytest.raises(CompositionError, match='not registered'):
        rewrite_references(data, {}, path_to_ref(main))


def test_rewrite_is_not_recursive(tmp_path: Path):
    # mid's own reference is left alone; mid is rewritten by its own registration.
    mid = _write(tmp_path / 'mid.nodl.yaml', 'nodl_version: 2\ninclude:\n  - ref: leaf.nodl.yaml\n')
    _write(tmp_path / 'leaf.nodl.yaml', 'nodl_version: 2\n')
    main = tmp_path / 'main.nodl.yaml'
    data = {'nodl_version': 2, 'include': [{'ref': 'mid.nodl.yaml'}]}
    out = rewrite_references(data, {mid: 'my_pkg/mid'}, path_to_ref(main))
    assert out['include'] == [{'ref': 'nodl://my_pkg/mid'}]
    assert 'leaf.nodl.yaml' in mid.read_text()
