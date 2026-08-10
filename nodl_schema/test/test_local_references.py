# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for ``local://`` references and their rewriting.

These use real files, since resolving against a document's location is the whole point.
"""

from pathlib import Path

import pytest

from nodl_schema import ResolutionError, dump_nodl, load_nodl, local_references, rewrite_local_references
from nodl_schema.local_resolver import LocalResolver, is_absolute, path_to_ref
from nodl_schema.models import History, NodlDocument, QosProfile, Reference, Reliability, TopicEndpoint
from nodl_schema.rewrite import default_name, rewrite_file

_QOS = QosProfile(history=History.SYSTEM_DEFAULT, reliability=Reliability.SYSTEM_DEFAULT)


def _pub_doc(name, *refs) -> NodlDocument:
    return NodlDocument(
        publishers=[TopicEndpoint(name=name, type='std_msgs/msg/String', qos=_QOS)],
        include=[Reference(ref=ref) for ref in refs],
    )


def _write(path: Path, doc: NodlDocument) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dump_nodl(doc))
    return path


# ---------------------------------------------------------------------------
# Resolving against the containing document
# ---------------------------------------------------------------------------


def test_relative_ref_resolves_against_the_document_directory(tmp_path: Path):
    _write(tmp_path / 'common' / 'telemetry.nodl.yaml', _pub_doc('/telem'))
    main = _write(tmp_path / 'my_node.nodl.yaml', _pub_doc('/own', 'local://common/telemetry.nodl.yaml'))
    doc = load_nodl(main.read_text(), base=main)
    assert sorted(p.name for p in doc.publishers) == ['/own', '/telem']


def test_open_file_supplies_its_own_base(tmp_path: Path):
    _write(tmp_path / 'shared.nodl.yaml', _pub_doc('/shared'))
    main = _write(tmp_path / 'main.nodl.yaml', NodlDocument(include=[Reference(ref='local://shared.nodl.yaml')]))
    with main.open() as f:
        doc = load_nodl(f)
    assert [p.name for p in doc.publishers] == ['/shared']


def test_nested_ref_is_relative_to_its_own_document(tmp_path: Path):
    # b/leaf is named relative to b/mid, not to the top-level document.
    _write(tmp_path / 'b' / 'leaf.nodl.yaml', _pub_doc('/leaf'))
    _write(tmp_path / 'b' / 'mid.nodl.yaml', NodlDocument(include=[Reference(ref='local://leaf.nodl.yaml')]))
    main = _write(tmp_path / 'top.nodl.yaml', NodlDocument(include=[Reference(ref='local://b/mid.nodl.yaml')]))
    doc = load_nodl(main.read_text(), base=main)
    assert [p.name for p in doc.publishers] == ['/leaf']


def test_relative_ref_may_walk_upward(tmp_path: Path):
    _write(tmp_path / 'shared' / 'base.nodl.yaml', _pub_doc('/base'))
    main = _write(
        tmp_path / 'nodl' / 'node.nodl.yaml', NodlDocument(include=[Reference(ref='local://../shared/base.nodl.yaml')])
    )
    doc = load_nodl(main.read_text(), base=main)
    assert [p.name for p in doc.publishers] == ['/base']


def test_relative_ref_without_a_base_raises(tmp_path: Path):
    with pytest.raises(ResolutionError, match='no location'):
        load_nodl(dump_nodl(NodlDocument(include=[Reference(ref='local://common/telemetry.nodl.yaml')])))


def test_relative_ref_inside_an_indexed_document_raises(tmp_path: Path):
    # A document fetched from the index is text with no location, so nothing in it can be relative.
    resolver = LocalResolver()
    with pytest.raises(ResolutionError, match='not a location in the source tree'):
        resolver.normalize('local://sibling.nodl.yaml', 'nodl://pkg/thing')


def test_missing_relative_ref_raises(tmp_path: Path):
    main = _write(tmp_path / 'main.nodl.yaml', NodlDocument(include=[Reference(ref='local://absent.nodl.yaml')]))
    with pytest.raises(ResolutionError, match='absent.nodl.yaml'):
        load_nodl(main.read_text(), base=main)


def test_cycle_is_detected_across_spellings(tmp_path: Path):
    # a -> b -> ./a, two spellings of one file. Normalizing before the check is what ends this.
    _write(tmp_path / 'a.nodl.yaml', NodlDocument(include=[Reference(ref='local://b.nodl.yaml')]))
    _write(tmp_path / 'b.nodl.yaml', NodlDocument(include=[Reference(ref='local://./a.nodl.yaml')]))
    main = tmp_path / 'a.nodl.yaml'
    with pytest.raises(ResolutionError, match='Double-inclusion'):
        load_nodl(main.read_text(), base=main)


def test_reference_looping_back_to_the_root_is_detected(tmp_path: Path):
    # Knowing the root's own origin is what makes this catchable at all.
    _write(tmp_path / 'other.nodl.yaml', NodlDocument(include=[Reference(ref='local://root.nodl.yaml')]))
    main = _write(tmp_path / 'root.nodl.yaml', NodlDocument(include=[Reference(ref='local://other.nodl.yaml')]))
    with pytest.raises(ResolutionError, match='Double-inclusion'):
        load_nodl(main.read_text(), base=main)


# ---------------------------------------------------------------------------
# local_references: what installation needs to know about
# ---------------------------------------------------------------------------


def test_local_references_is_transitive(tmp_path: Path):
    leaf = _write(tmp_path / 'leaf.nodl.yaml', NodlDocument())
    mid = _write(tmp_path / 'mid.nodl.yaml', NodlDocument(include=[Reference(ref='local://leaf.nodl.yaml')]))
    main = _write(tmp_path / 'main.nodl.yaml', NodlDocument(include=[Reference(ref='local://mid.nodl.yaml')]))
    found = local_references(load_nodl(main.read_text(), resolve=False), path_to_ref(main))
    assert found == [mid, leaf]


def test_local_references_ignores_nodl_refs(tmp_path: Path):
    main = _write(tmp_path / 'main.nodl.yaml', NodlDocument(include=[Reference(ref='nodl://other/thing')]))
    assert local_references(load_nodl(main.read_text(), resolve=False), path_to_ref(main)) == []


def test_local_references_survives_a_cycle(tmp_path: Path):
    a = _write(tmp_path / 'a.nodl.yaml', NodlDocument(include=[Reference(ref='local://b.nodl.yaml')]))
    b = _write(tmp_path / 'b.nodl.yaml', NodlDocument(include=[Reference(ref='local://a.nodl.yaml')]))
    found = local_references(load_nodl(a.read_text(), resolve=False), path_to_ref(a))
    assert found == [b, a]


def test_local_references_deduplicates(tmp_path: Path):
    shared = _write(tmp_path / 'shared.nodl.yaml', NodlDocument())
    main = _write(
        tmp_path / 'main.nodl.yaml',
        NodlDocument(include=[Reference(ref='local://shared.nodl.yaml'), Reference(ref='local://./shared.nodl.yaml')]),
    )
    found = local_references(load_nodl(main.read_text(), resolve=False), path_to_ref(main))
    assert found == [shared]


# ---------------------------------------------------------------------------
# Rewriting for installation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    'filename,expected',
    [('telemetry.nodl.yaml', 'telemetry'), ('a.nodl.json', 'a'), ('plain.yaml', 'plain'), ('bare', 'bare')],
)
def test_default_name_strips_extensions(filename, expected):
    assert default_name(Path('/x') / filename) == expected


def test_rewrite_replaces_local_ref_with_registered_name(tmp_path: Path):
    shared = _write(tmp_path / 'common' / 'telemetry.nodl.yaml', NodlDocument())
    main = tmp_path / 'my_node.nodl.yaml'
    doc = NodlDocument(include=[Reference(ref='local://common/telemetry.nodl.yaml')])
    out = rewrite_local_references(doc, origin=path_to_ref(main), package='my_pkg', names={shared: 'telemetry'})
    assert [r.ref for r in out.include] == ['nodl://my_pkg/telemetry']


def test_rewrite_honours_a_name_carrying_its_own_package(tmp_path: Path):
    # A document registered under a PACKAGE override belongs to that package, not the building one.
    shared = _write(tmp_path / 'shared.nodl.yaml', NodlDocument())
    main = tmp_path / 'my_node.nodl.yaml'
    doc = NodlDocument(include=[Reference(ref='local://shared.nodl.yaml')])
    out = rewrite_local_references(doc, origin=path_to_ref(main), package='my_pkg', names={shared: 'other_pkg/thing'})
    assert [r.ref for r in out.include] == ['nodl://other_pkg/thing']


def test_rewrite_leaves_nodl_refs_alone(tmp_path: Path):
    doc = NodlDocument(include=[Reference(ref='nodl://other_pkg/thing')])
    out = rewrite_local_references(doc, origin=path_to_ref(tmp_path / 'x.nodl.yaml'), package='my_pkg', names={})
    assert [r.ref for r in out.include] == ['nodl://other_pkg/thing']


def test_rewrite_changes_nothing_else(tmp_path: Path):
    shared = _write(tmp_path / 'shared.nodl.yaml', NodlDocument())
    doc = _pub_doc('/status', 'local://shared.nodl.yaml')
    doc.description = 'a node'
    out = rewrite_local_references(
        doc, origin=path_to_ref(tmp_path / 'x.nodl.yaml'), package='my_pkg', names={shared: 'shared'}
    )
    assert out.description == 'a node'
    assert [p.name for p in out.publishers] == ['/status']
    # Entities are not merged in; only the reference changed.
    assert out.subscriptions is None


def test_rewrite_does_not_mutate_input(tmp_path: Path):
    shared = _write(tmp_path / 'shared.nodl.yaml', NodlDocument())
    doc = NodlDocument(include=[Reference(ref='local://shared.nodl.yaml')])
    rewrite_local_references(doc, origin=path_to_ref(tmp_path / 'x.nodl.yaml'), package='p', names={shared: 'shared'})
    assert [r.ref for r in doc.include] == ['local://shared.nodl.yaml']


def test_rewrite_of_an_unregistered_reference_raises(tmp_path: Path):
    _write(tmp_path / 'shared.nodl.yaml', NodlDocument())
    doc = NodlDocument(include=[Reference(ref='local://shared.nodl.yaml')])
    with pytest.raises(ResolutionError, match='not registered'):
        rewrite_local_references(doc, origin=path_to_ref(tmp_path / 'x.nodl.yaml'), package='p', names={})


def test_rewrite_is_not_recursive(tmp_path: Path):
    # mid's own reference is left alone; mid is rewritten by its own registration.
    mid = _write(tmp_path / 'mid.nodl.yaml', NodlDocument(include=[Reference(ref='local://leaf.nodl.yaml')]))
    _write(tmp_path / 'leaf.nodl.yaml', NodlDocument())
    doc = NodlDocument(include=[Reference(ref='local://mid.nodl.yaml')])
    out = rewrite_local_references(
        doc, origin=path_to_ref(tmp_path / 'main.nodl.yaml'), package='p', names={mid: 'mid'}
    )
    assert [r.ref for r in out.include] == ['nodl://p/mid']
    assert 'local://leaf.nodl.yaml' in mid.read_text()


def test_rewrite_file_without_local_refs_copies_bytes(tmp_path: Path):
    # Most documents have nothing to rewrite; those must install exactly as authored.
    source = _write(tmp_path / 'main.nodl.yaml', _pub_doc('/only'))
    output = tmp_path / 'gen' / 'main.nodl.yaml'
    assert rewrite_file(source, output, package='p') is False
    assert output.read_bytes() == source.read_bytes()


def test_rewrite_file_preserves_the_json_frontend(tmp_path: Path):
    shared = _write(tmp_path / 'shared.nodl.yaml', NodlDocument())
    source = tmp_path / 'main.nodl.json'
    source.write_text('{"nodl_version": 2, "include": [{"ref": "local://shared.nodl.yaml"}]}\n')
    output = tmp_path / 'out.nodl.json'
    assert rewrite_file(source, output, package='p', names={shared: 'shared'}) is True
    assert '"nodl_version": 2' in output.read_text()
    assert 'nodl://p/shared' in output.read_text()


def test_rewritten_document_still_validates(tmp_path: Path):
    # What gets installed has to be a valid NoDL document in its own right.
    shared = _write(tmp_path / 'shared.nodl.yaml', NodlDocument())
    source = _write(tmp_path / 'main.nodl.yaml', _pub_doc('/status', 'local://shared.nodl.yaml'))
    output = tmp_path / 'out.nodl.yaml'
    rewrite_file(source, output, package='p', names={shared: 'shared'})
    doc = load_nodl(output.read_text(), resolve=False)
    assert [r.ref for r in doc.include] == ['nodl://p/shared']


# ---------------------------------------------------------------------------
# Reference forms
# ---------------------------------------------------------------------------


def test_absolute_local_ref_is_left_alone_by_normalize():
    resolver = LocalResolver()
    absolute = path_to_ref('/tmp/x.nodl.yaml')
    assert is_absolute(absolute)
    assert resolver.normalize(absolute, None) == absolute


@pytest.mark.parametrize('ref', ['local://x.yaml', 'local://a/b.yaml'])
def test_local_resolver_handles_local_refs(ref):
    assert LocalResolver().handles(ref)


@pytest.mark.parametrize('ref', ['nodl://pkg/x', 'test://x', ''])
def test_local_resolver_ignores_other_schemes(ref):
    assert not LocalResolver().handles(ref)
