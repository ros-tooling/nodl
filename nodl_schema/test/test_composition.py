# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for NoDL document composition (the ``include`` key)."""

import tempfile
from pathlib import Path

import pytest

from nodl_schema import (
    AmentIndexResolver,
    ResolutionError,
    dump_nodl,
    get_resolvers,
    load_nodl,
    parse_nodl,
    register_resolver,
    resolve_document,
    resolver_registered,
    unregister_resolver,
)
from nodl_schema.composition import MergeError, merge_documents, resolve, resolver_for
from nodl_schema.models import (
    History,
    NodlDocument,
    ParameterDefinition,
    QosProfile,
    Reference,
    Reliability,
    ServiceEndpoint,
    TopicEndpoint,
)

_QOS = QosProfile(history=History.SYSTEM_DEFAULT, reliability=Reliability.SYSTEM_DEFAULT)


def _topic(name, type_='std_msgs/msg/String') -> TopicEndpoint:
    return TopicEndpoint(
        name=name,
        type=type_,
        qos=_QOS,
    )


def _service(name, type_='std_srvs/srv/Trigger') -> ServiceEndpoint:
    return ServiceEndpoint(name=name, type=type_)


def _pub_doc(name, *refs) -> NodlDocument:
    return NodlDocument(
        publishers=[
            _topic(name),
        ],
        include=_refs(*refs),
    )


def _sub_doc(name, *refs) -> NodlDocument:
    return NodlDocument(subscriptions=[_topic(name)], include=_refs(*refs))


def _param_doc(**params) -> NodlDocument:
    """A document declaring parameters, given as ``name='type'`` pairs."""
    return NodlDocument(parameters={name: ParameterDefinition(type=type_) for name, type_ in params.items()})


def _refs(*refs) -> list[Reference]:
    return [Reference(ref=ref) for ref in refs]


def _including(*refs) -> NodlDocument:
    """A document whose only content is what it includes."""
    return NodlDocument(include=_refs(*refs))


class FakeResolver:
    """Resolves an in-memory ``test://`` reference format.

    Documents go in as models and come out as a ``Path`` to a temp file, since that is
    what a resolver returns.
    Use ``add_text`` for content a model cannot hold, such as a deliberately invalid document.
    """

    scheme = 'test://'

    def __init__(self, docs: dict[str, NodlDocument] | None = None):
        self.docs: dict[str, Path] = {}
        self.calls: list[str] = []
        self._dir = Path(tempfile.mkdtemp())
        self._n = 0
        for name, doc in (docs or {}).items():
            self.add(name, doc)

    def add(self, name: str, doc: NodlDocument) -> str:
        """Register ``doc`` as ``test://<name>`` and return the ref that includes it."""
        return self.add_text(name, dump_nodl(doc))

    def add_text(self, name: str, text: str) -> str:
        """Register raw text, for documents that are deliberately not valid NoDL."""
        ref = f'{self.scheme}{name}'
        # Refs may contain '/', so name the file by insertion order rather than by ref.
        path = self._dir / f'{self._n}.nodl.yaml'
        self._n += 1
        path.write_text(text)
        self.docs[ref] = path
        return ref

    def handles(self, ref: str) -> bool:
        return ref.startswith(self.scheme)

    def resolve(self, ref: str, origin: Path | None = None) -> Path:
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
    base = NodlDocument(publishers=[_topic('/base')], include=_refs(ref))
    merged = merge_documents(resolve_document(base).flatten())
    assert merged.include is None
    assert merged.publishers
    assert merged.subscriptions
    assert [p.name for p in merged.publishers] == ['/base']
    assert [s.name for s in merged.subscriptions] == ['/extra']


def test_include_merges_parameters(docs):
    ref = docs.add('params', _param_doc(gain='double'))
    base = NodlDocument(parameters={'rate': ParameterDefinition(type='int')}, include=_refs(ref))
    merged = merge_documents(resolve_document(base).flatten())
    assert merged.parameters
    assert set(merged.parameters) == {'rate', 'gain'}


def test_nested_include_is_resolved_recursively(docs):
    inner = docs.add('b', _pub_doc('/b'))
    ref = docs.add('a', _pub_doc('/a', inner))
    merged = merge_documents(resolve_document(_including(ref)).flatten())
    assert merged.publishers
    assert sorted(p.name for p in merged.publishers) == ['/a', '/b']


def test_input_document_is_not_mutated(docs):
    ref = docs.add('x', _pub_doc('/x'))
    base = _including(ref)
    merge_documents(resolve_document(base).flatten())
    assert base.include
    assert [r.ref for r in base.include] == [ref]
    assert base.publishers is None


def test_document_without_includes_touches_no_resolver(docs):
    base = NodlDocument(publishers=[_topic('/only')])
    merged = merge_documents(resolve_document(base).flatten())
    assert docs.calls == []
    assert merged.publishers
    assert [p.name for p in merged.publishers] == ['/only']


# ---------------------------------------------------------------------------
# resolve_document tree structure
# ---------------------------------------------------------------------------


def test_resolve_no_includes_returns_empty_tree(docs):
    base = NodlDocument(publishers=[_topic('/only')])
    tree = resolve_document(base)
    assert tree.root_doc is base
    assert tree.resolved_includes == []


def test_resolve_single_include_has_one_child(docs):
    ref = docs.add('x', _pub_doc('/x'))
    tree = resolve_document(_including(ref))
    assert len(tree.resolved_includes) == 1
    child = tree.resolved_includes[0]
    assert child.ref == ref
    assert child.doc.publishers[0].name == '/x'
    assert child.resolved_includes == []


def test_resolve_nested_includes_builds_tree(docs):
    inner = docs.add('inner', _pub_doc('/inner'))
    outer = docs.add('outer', _pub_doc('/outer', inner))
    tree = resolve_document(_including(outer))
    assert len(tree.resolved_includes) == 1
    outer_node = tree.resolved_includes[0]
    assert outer_node.ref == outer
    assert len(outer_node.resolved_includes) == 1
    inner_node = outer_node.resolved_includes[0]
    assert inner_node.ref == inner
    assert inner_node.resolved_includes == []


def test_flatten_nested_tree_contains_all_documents(docs):
    inner = docs.add('inner', _pub_doc('/inner'))
    outer = docs.add('outer', _pub_doc('/outer', inner))
    base = NodlDocument(publishers=[_topic('/root')], include=_refs(outer))
    flat = resolve_document(base).flatten()
    names = {d.publishers[0].name for d in flat if d.publishers}
    assert names == {'/root', '/outer', '/inner'}


def test_flatten_no_includes_returns_only_root(docs):
    base = NodlDocument(publishers=[_topic('/only')])
    assert resolve_document(base).flatten() == [base]


# ---------------------------------------------------------------------------
# Collisions (error-on-collision policy)
# ---------------------------------------------------------------------------


def test_collision_between_base_and_include_errors(docs):
    ref = docs.add('dup', _pub_doc('/status'))
    base = NodlDocument(publishers=[_topic('/status')], include=_refs(ref))
    with pytest.raises(MergeError, match='/status'):
        merge_documents(resolve_document(base).flatten())


def test_collision_between_two_includes_errors(docs):
    one = docs.add('one', _pub_doc('/shared'))
    two = docs.add('two', _pub_doc('/shared'))
    with pytest.raises(MergeError, match='/shared'):
        merge_documents(resolve_document(_including(one, two)).flatten())


def test_parameter_collision_errors(docs):
    ref = docs.add('p', _param_doc(gain='double'))
    base = NodlDocument(parameters={'gain': ParameterDefinition(type='int')}, include=_refs(ref))
    with pytest.raises(MergeError, match='gain'):
        merge_documents(resolve_document(base).flatten())


def test_service_collision_errors(docs):
    ref = docs.add('svc', NodlDocument(service_servers=[_service('/reset')]))
    base = NodlDocument(service_servers=[_service('/reset')], include=_refs(ref))
    with pytest.raises(MergeError, match='/reset'):
        merge_documents(resolve_document(base).flatten())


def test_same_name_different_category_is_allowed(docs):
    # A publisher and a subscription may share a topic name; they are different categories.
    ref = docs.add('sub', _sub_doc('/topic'))
    base = NodlDocument(publishers=[_topic('/topic')], include=_refs(ref))
    merged = merge_documents(resolve_document(base).flatten())
    assert merged.publishers
    assert merged.publishers[0].name == '/topic'
    assert merged.subscriptions
    assert merged.subscriptions[0].name == '/topic'


def test_diamond_surfaces_as_a_collision(docs):
    # Two includes pulling in the same third document is a duplicate, not a merge.
    shared = docs.add('shared', _pub_doc('/shared'))
    left = docs.add('left', _including(shared))
    right = docs.add('right', _including(shared))
    with pytest.raises(ResolutionError, match='/shared|nclusion'):
        merge_documents(resolve_document(_including(left, right)).flatten())


# ---------------------------------------------------------------------------
# Cycles and failures
# ---------------------------------------------------------------------------


def test_cycle_is_detected(docs):
    ref = docs.add('a', _including('test://b'))
    docs.add('b', _including('test://a'))
    with pytest.raises(ResolutionError):
        resolve_document(_including(ref))


def test_self_reference_is_detected(docs):
    ref = docs.add('a', _including('test://a'))
    with pytest.raises(ResolutionError):
        resolve_document(_including(ref))


def test_unresolvable_ref_raises(docs):
    # The scheme is handled, but the document behind it is not there.
    with pytest.raises(Exception):
        resolve_document(_including('test://missing'))


def test_ref_no_resolver_handles_raises(docs):
    # A scheme no resolver claims fails before anything is fetched.
    with pytest.raises(ResolutionError, match='[Nn]o registered resolver handles'):
        resolve_document(_including('ftp://example.com/x.nodl.yaml'))
    assert docs.calls == []


def test_included_document_is_schema_validated(docs):
    # Authored as text, because a model cannot hold the bad parameter type under test.
    ref = docs.add_text('bad', 'nodl_version: 2\nparameters:\n  p: {type: not_a_type}\n')
    with pytest.raises(Exception):
        resolve_document(_including(ref))


def test_included_non_mapping_raises(docs):
    ref = docs.add_text('list', '- just a list\n')
    with pytest.raises(ValueError, match='mapping'):
        resolve_document(_including(ref))


# ---------------------------------------------------------------------------
# load/parse nodl
# ---------------------------------------------------------------------------


def test_load_nodl_resolves_through_the_registry(docs, tmp_path):
    ref = docs.add('extra', _sub_doc('/extra'))
    source = tmp_path / 'root.nodl.yaml'
    source.write_text(dump_nodl(_including(ref)))
    doc = load_nodl(source)
    assert doc.subscriptions
    assert doc.subscriptions[0].name == '/extra'
    # The include key is consumed once resolved.
    assert doc.include is None


def test_load_nodl_no_resolve_keeps_include(docs, tmp_path):
    source = tmp_path / 'root.nodl.yaml'
    source.write_text(dump_nodl(_including('test://extra')))
    doc = load_nodl(source, resolve=False)
    assert doc.include
    assert [r.ref for r in doc.include] == ['test://extra']
    assert docs.calls == []


def test_load_nodl_without_include_does_not_touch_resolver(docs):
    parse_nodl(dump_nodl(NodlDocument()))
    assert docs.calls == []


def test_load_nodl_merges_the_resolved_documents(docs, tmp_path):
    ref = docs.add('extra', _sub_doc('/extra'))
    source = tmp_path / 'root.nodl.yaml'
    source.write_text(dump_nodl(NodlDocument(publishers=[_topic('/base')], include=_refs(ref))))
    doc = load_nodl(source)
    assert doc.publishers
    assert [p.name for p in doc.publishers] == ['/base']
    assert doc.subscriptions
    assert [s.name for s in doc.subscriptions] == ['/extra']


# ---------------------------------------------------------------------------
# Resolver registration
# ---------------------------------------------------------------------------


def test_registry_finds_the_resolver_that_handles_a_ref(docs):
    assert resolver_for('test://x') is docs
    assert isinstance(resolver_for('nodl://pkg/x'), AmentIndexResolver)
    assert resolver_for('ftp://example.com/x') is None


def test_registry_searches_most_recently_registered_first():
    # A later registration shadows an earlier one handling the same scheme.
    first, second = FakeResolver(), FakeResolver()
    with resolver_registered(first), resolver_registered(second):
        assert resolver_for('test://x') is second


def test_registry_unregister_restores_the_shadowed_resolver():
    first, second = FakeResolver(), FakeResolver()
    with resolver_registered(first):
        with resolver_registered(second):
            assert resolver_for('test://x') is second
        assert resolver_for('test://x') is first


def test_registry_unregister_removes_only_the_latest_registration():
    # An inner scope re-registering the same resolver undoes only its own registration.
    resolver = FakeResolver()
    with resolver_registered(resolver):
        with resolver_registered(resolver):
            pass
        assert resolver_for('test://x') is resolver


def test_registry_unregister_of_an_absent_resolver_raises():
    with pytest.raises(LookupError):
        unregister_resolver(FakeResolver())


def test_registry_rejects_a_non_resolver():
    with pytest.raises(TypeError, match='not a Resolver'):
        register_resolver(object())  # pyright: ignore


def test_registry_resolve_reports_an_unhandled_scheme():
    with pytest.raises(ResolutionError, match='[Nn]o registered resolver handles'):
        resolve('test://x')


def test_resolver_failure_propagates_unchanged(docs):
    # resolve() does not wrap what a resolver raises, so failures arrive in the resolver's terms.
    with pytest.raises(FileNotFoundError, match='test://absent'):
        resolve('test://absent')


# ---------------------------------------------------------------------------
# Scoped registration
# ---------------------------------------------------------------------------


def test_ament_resolver_is_registered_by_default():
    assert any(isinstance(r, AmentIndexResolver) for r in get_resolvers())


def test_resolver_registered_adds_and_removes():
    resolver = FakeResolver()
    assert resolver_for('test://x') is None
    with resolver_registered(resolver):
        assert resolver_for('test://x') is resolver
    assert resolver_for('test://x') is None


def test_resolver_registered_removes_even_when_the_block_raises():
    # Otherwise a failing test leaks its resolver into every test after it.
    resolver = FakeResolver()
    with pytest.raises(ValueError):
        with resolver_registered(resolver):
            raise ValueError('boom')
    assert resolver_for('test://x') is None


def test_registering_shadows_the_built_in_resolver():
    # Registering over a built-in scheme replaces it for the duration of the block.
    class NodlShadow(FakeResolver):
        scheme = 'nodl://'

    shadow = NodlShadow()
    ref = shadow.add('pkg/thing', _pub_doc('/shadowed'))
    with resolver_registered(shadow):
        merged = merge_documents(resolve_document(_including(ref)).flatten())
    assert merged.publishers
    assert [p.name for p in merged.publishers] == ['/shadowed']
    assert isinstance(resolver_for(ref), AmentIndexResolver)


def test_register_resolver_without_a_scope_persists_until_removed():
    resolver = FakeResolver()
    register_resolver(resolver)
    try:
        assert resolver_for('test://x') is resolver
    finally:
        unregister_resolver(resolver)
    assert resolver_for('test://x') is None


# ---------------------------------------------------------------------------
# codegen field
# ---------------------------------------------------------------------------


def test_codegen_on_included_document_survives_resolution(docs):
    codegen = {'cpp': {'role': 'base_class', 'header': 'rclcpp/rclcpp.hpp'}}
    ref = docs.add('with_cg', NodlDocument(publishers=[_topic('/t')], codegen=codegen))
    resolved = resolve_document(_including(ref))
    included = resolved.resolved_includes[0].doc
    assert included.codegen == codegen
