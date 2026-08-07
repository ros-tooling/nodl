# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for NoDL document composition (the ``include`` key).

Resolution is exercised through a fake in-memory resolver, registered under its
own ``test://`` scheme, so these tests need neither an ament index nor network
access. Nothing is passed a resolver: the ``docs`` fixture registers one for the
duration of a test and ``load_nodl``/``resolve_document`` reach it through the
registry, which is the arrangement being tested as much as it is the setup.

AmentIndexResolver's own URI handling is tested here against a stubbed ament
lookup; end-to-end resolution through a real index lives in test_ament_nodl.
"""

import pytest

from nodl_schema import load_nodl
from nodl_schema.composition import (
    AmentIndexResolver,
    CompositionError,
    ResolverRegistry,
    default_registry,
    register_resolver,
    resolve_document,
    resolver_registered,
    unregister_resolver,
)

_MIN_QOS = {'history': 'SYSTEM_DEFAULT', 'reliability': 'SYSTEM_DEFAULT'}
_QOS_YAML = 'qos: {history: SYSTEM_DEFAULT, reliability: SYSTEM_DEFAULT}'


def _pub(name, type_='std_msgs/msg/String'):
    return {'name': name, 'type': type_, 'qos': _MIN_QOS}


def _pub_doc(name):
    return f'nodl_version: 2\npublishers:\n  - name: {name}\n    type: std_msgs/msg/String\n    {_QOS_YAML}\n'


def _sub_doc(name):
    return f'nodl_version: 2\nsubscriptions:\n  - name: {name}\n    type: std_msgs/msg/String\n    {_QOS_YAML}\n'


def _including(*refs):
    return {'nodl_version': 2, 'include': [{'ref': ref} for ref in refs]}


class FakeResolver:
    """Resolves an in-memory ``test://`` namespace.

    A scheme of its own is what lets this stand alongside the built-in resolver rather than
    having to displace it, so a test says what it wants resolvable and nothing else changes.
    """

    scheme = 'test://'

    def __init__(self, docs: dict | None = None):
        self.docs = dict(docs or {})
        self.calls: list[str] = []

    def add(self, name: str, text: str) -> str:
        """Register document ``text`` as ``test://<name>`` and return the ref to include."""
        ref = f'{self.scheme}{name}'
        self.docs[ref] = text
        return ref

    def handles(self, ref: str) -> bool:
        return ref.startswith(self.scheme)

    def resolve(self, ref: str) -> str:
        self.calls.append(ref)
        try:
            return self.docs[ref]
        except KeyError:
            raise FileNotFoundError(ref)


@pytest.fixture
def docs():
    """A fake resolver, registered for the duration of one test."""
    with resolver_registered(FakeResolver()) as resolver:
        yield resolver


# ---------------------------------------------------------------------------
# Merging
# ---------------------------------------------------------------------------


def test_single_include_merges_entities(docs):
    ref = docs.add('extra', _sub_doc('/extra'))
    base = {'nodl_version': 2, 'include': [{'ref': ref}], 'publishers': [_pub('/base')]}
    merged = resolve_document(base)
    assert 'include' not in merged
    assert [p['name'] for p in merged['publishers']] == ['/base']
    assert [s['name'] for s in merged['subscriptions']] == ['/extra']


def test_include_merges_parameters(docs):
    ref = docs.add('params', 'nodl_version: 2\nparameters:\n  gain: {type: double}\n')
    base = {'nodl_version': 2, 'include': [{'ref': ref}], 'parameters': {'rate': {'type': 'int'}}}
    merged = resolve_document(base)
    assert set(merged['parameters']) == {'rate', 'gain'}


def test_nested_include_is_resolved_recursively(docs):
    docs.add('b', _pub_doc('/b'))
    ref = docs.add(
        'a',
        f'nodl_version: 2\ninclude:\n  - ref: test://b\npublishers:\n'
        f'  - name: /a\n    type: std_msgs/msg/String\n    {_QOS_YAML}\n',
    )
    merged = resolve_document(_including(ref))
    assert sorted(p['name'] for p in merged['publishers']) == ['/a', '/b']


def test_input_document_is_not_mutated(docs):
    ref = docs.add('x', _pub_doc('/x'))
    base = _including(ref)
    resolve_document(base)
    assert base['include'] == [{'ref': ref}]
    assert 'publishers' not in base


def test_document_without_includes_touches_no_resolver(docs):
    merged = resolve_document({'nodl_version': 2, 'publishers': [_pub('/only')]})
    assert docs.calls == []
    assert merged['publishers'] == [_pub('/only')]


# ---------------------------------------------------------------------------
# Collisions (error-on-collision policy)
# ---------------------------------------------------------------------------


def test_collision_between_base_and_include_errors(docs):
    ref = docs.add('dup', _pub_doc('/status'))
    base = {'nodl_version': 2, 'include': [{'ref': ref}], 'publishers': [_pub('/status')]}
    with pytest.raises(CompositionError, match='/status'):
        resolve_document(base)


def test_collision_between_two_includes_errors(docs):
    one = docs.add('one', _pub_doc('/shared'))
    two = docs.add('two', _pub_doc('/shared'))
    with pytest.raises(CompositionError, match='/shared'):
        resolve_document(_including(one, two))


def test_parameter_collision_errors(docs):
    ref = docs.add('p', 'nodl_version: 2\nparameters:\n  gain: {type: double}\n')
    base = {'nodl_version': 2, 'include': [{'ref': ref}], 'parameters': {'gain': {'type': 'int'}}}
    with pytest.raises(CompositionError, match='gain'):
        resolve_document(base)


def test_same_name_different_category_is_allowed(docs):
    # A publisher and a subscription may share a topic name; they are different categories.
    ref = docs.add('sub', _sub_doc('/topic'))
    base = {'nodl_version': 2, 'include': [{'ref': ref}], 'publishers': [_pub('/topic')]}
    merged = resolve_document(base)
    assert merged['publishers'][0]['name'] == '/topic'
    assert merged['subscriptions'][0]['name'] == '/topic'


def test_diamond_surfaces_as_a_collision(docs):
    # Known limitation of the strict policy: two includes pulling in the same third document is
    # a duplicate rather than a merge, because dedup across resolution paths is not performed.
    docs.add('shared', _pub_doc('/shared'))
    left = docs.add('left', 'nodl_version: 2\ninclude:\n  - ref: test://shared\n')
    right = docs.add('right', 'nodl_version: 2\ninclude:\n  - ref: test://shared\n')
    with pytest.raises(CompositionError, match='/shared'):
        resolve_document(_including(left, right))


# ---------------------------------------------------------------------------
# Cycles and failures
# ---------------------------------------------------------------------------


def test_cycle_is_detected(docs):
    ref = docs.add('a', 'nodl_version: 2\ninclude:\n  - ref: test://b\n')
    docs.add('b', 'nodl_version: 2\ninclude:\n  - ref: test://a\n')
    with pytest.raises(CompositionError, match='cycle'):
        resolve_document(_including(ref))


def test_self_reference_is_detected(docs):
    ref = docs.add('a', 'nodl_version: 2\ninclude:\n  - ref: test://a\n')
    with pytest.raises(CompositionError, match='cycle'):
        resolve_document(_including(ref))


def test_unresolvable_ref_raises_composition_error(docs):
    # Handled by the fake, which then cannot find it: a resolver's own failure is normalized.
    with pytest.raises(CompositionError, match='test://missing'):
        resolve_document(_including('test://missing'))


def test_ref_no_resolver_handles_raises(docs):
    # The scheme selects the resolver, so a scheme nothing claims is the error, not a bad path.
    with pytest.raises(CompositionError, match='no registered resolver handles'):
        resolve_document(_including('ftp://example.com/x.nodl.yaml'))
    assert docs.calls == []


def test_included_document_is_schema_validated(docs):
    # The included document is itself invalid (bad parameter type); resolution must surface it.
    ref = docs.add('bad', 'nodl_version: 2\nparameters:\n  p: {type: not_a_type}\n')
    with pytest.raises(Exception):
        resolve_document(_including(ref))


def test_included_non_mapping_raises(docs):
    ref = docs.add('list', '- just a list\n')
    with pytest.raises(CompositionError, match='mapping'):
        resolve_document(_including(ref))


# ---------------------------------------------------------------------------
# load_nodl integration -- no resolver argument anywhere
# ---------------------------------------------------------------------------


def test_load_nodl_resolves_through_the_registry(docs):
    ref = docs.add('extra', _sub_doc('/extra'))
    doc = load_nodl(f'nodl_version: 2\ninclude:\n  - ref: {ref}\n')
    assert doc.subscriptions[0].name == '/extra'
    # The include key is consumed once resolved.
    assert doc.include is None


def test_load_nodl_no_resolve_keeps_include(docs):
    doc = load_nodl('nodl_version: 2\ninclude:\n  - ref: test://extra\n', resolve=False)
    assert doc.include[0].ref == 'test://extra'
    assert docs.calls == []


def test_load_nodl_without_include_does_not_touch_resolver(docs):
    load_nodl('nodl_version: 2\n')
    assert docs.calls == []


def test_load_nodl_revalidates_the_merged_document(docs):
    # The merge can only produce a valid document from valid parts, but the check is cheap and
    # keeps a merge bug from reaching a caller as a typed model.
    ref = docs.add('extra', _sub_doc('/extra'))
    doc = load_nodl(
        f'nodl_version: 2\npublishers:\n  - name: /base\n    type: std_msgs/msg/String\n    {_QOS_YAML}\n'
        f'include:\n  - ref: {ref}\n'
    )
    assert [p.name for p in doc.publishers] == ['/base']
    assert [s.name for s in doc.subscriptions] == ['/extra']


# ---------------------------------------------------------------------------
# ResolverRegistry
# ---------------------------------------------------------------------------


def test_registry_finds_the_resolver_that_handles_a_ref():
    fake = FakeResolver()
    registry = ResolverRegistry((AmentIndexResolver(), fake))
    assert registry.resolver_for('test://x') is fake
    assert isinstance(registry.resolver_for('nodl://pkg/x'), AmentIndexResolver)
    assert registry.resolver_for('ftp://example.com/x') is None


def test_registry_searches_most_recently_registered_first():
    # Shadowing is what lets a scoped registration stand in for a form already handled.
    first, second = FakeResolver(), FakeResolver()
    registry = ResolverRegistry((first,))
    registry.register(second)
    assert registry.resolver_for('test://x') is second


def test_registry_unregister_restores_the_shadowed_resolver():
    first, second = FakeResolver(), FakeResolver()
    registry = ResolverRegistry((first,))
    registry.register(second)
    registry.unregister(second)
    assert registry.resolver_for('test://x') is first


def test_registry_unregister_removes_only_the_latest_registration():
    # Nesting: an inner scope that re-registers something already present undoes only its own.
    resolver = FakeResolver()
    registry = ResolverRegistry((resolver,))
    registry.register(resolver)
    registry.unregister(resolver)
    assert registry.resolver_for('test://x') is resolver


def test_registry_unregister_of_an_absent_resolver_raises():
    with pytest.raises(LookupError):
        ResolverRegistry().unregister(FakeResolver())


def test_registry_rejects_a_non_resolver():
    with pytest.raises(TypeError, match='not a Resolver'):
        ResolverRegistry().register(object())


def test_registry_resolve_reports_an_unhandled_scheme():
    with pytest.raises(CompositionError, match='no registered resolver handles'):
        ResolverRegistry().resolve('test://x')


def test_registry_resolve_normalizes_a_resolver_failure():
    registry = ResolverRegistry((FakeResolver(),))
    with pytest.raises(CompositionError, match='test://absent'):
        registry.resolve('test://absent')


# ---------------------------------------------------------------------------
# The default registry and scoped registration
# ---------------------------------------------------------------------------


def test_ament_resolver_is_registered_by_default():
    assert any(isinstance(r, AmentIndexResolver) for r in default_registry())


def test_resolver_registered_adds_and_removes():
    resolver = FakeResolver()
    assert default_registry().resolver_for('test://x') is None
    with resolver_registered(resolver):
        assert default_registry().resolver_for('test://x') is resolver
    assert default_registry().resolver_for('test://x') is None


def test_resolver_registered_removes_even_when_the_block_raises():
    # Otherwise one failing test leaks a resolver into every test after it.
    resolver = FakeResolver()
    with pytest.raises(ValueError):
        with resolver_registered(resolver):
            raise ValueError('boom')
    assert default_registry().resolver_for('test://x') is None


def test_registering_shadows_the_built_in_resolver():
    # A test can stand in for the ament index without one being present.
    class NodlShadow(FakeResolver):
        scheme = 'nodl://'

    shadow = NodlShadow()
    shadow.add('pkg/thing', _pub_doc('/shadowed'))
    with resolver_registered(shadow):
        merged = resolve_document(_including('nodl://pkg/thing'))
    assert [p['name'] for p in merged['publishers']] == ['/shadowed']
    assert isinstance(default_registry().resolver_for('nodl://pkg/thing'), AmentIndexResolver)


def test_register_resolver_without_a_scope_persists_until_removed():
    resolver = FakeResolver()
    register_resolver(resolver)
    try:
        assert default_registry().resolver_for('test://x') is resolver
    finally:
        unregister_resolver(resolver)
    assert default_registry().resolver_for('test://x') is None


# ---------------------------------------------------------------------------
# AmentIndexResolver
# ---------------------------------------------------------------------------


@pytest.mark.parametrize('ref', ['nodl://sensor_common/imu_driver', 'nodl://pkg/x'])
def test_ament_resolver_handles_nodl_refs(ref):
    assert AmentIndexResolver().handles(ref)


@pytest.mark.parametrize('ref', ['test://x', 'common/telemetry.nodl.yaml', 'ftp://example.com/x.yaml', ''])
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
    # The schema no longer checks the body of a nodl:// ref, so this is the only check of it.
    with pytest.raises(CompositionError, match='expected nodl://'):
        AmentIndexResolver().resolve(ref)
