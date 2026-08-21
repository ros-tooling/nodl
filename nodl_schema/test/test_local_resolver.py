# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for ``local://`` references and their rewriting.

These use real files, since resolving against a document's location is the whole point.
"""

from pathlib import Path

import pytest

from nodl_schema import ResolutionError, dump_nodl, load_nodl
from nodl_schema.local_resolver import LocalResolver
from nodl_schema.models import History, NodlDocument, QosProfile, Reference, Reliability, TopicEndpoint


def _write(path: Path, doc: NodlDocument) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = dump_nodl(doc)
    path.write_text(text)
    return path


def _pub_doc(name, *refs) -> NodlDocument:
    qos = QosProfile(history=History.SYSTEM_DEFAULT, reliability=Reliability.SYSTEM_DEFAULT)
    return NodlDocument(
        publishers=[TopicEndpoint(name=name, type='std_msgs/msg/String', qos=qos)],
        include=[Reference(ref=ref) for ref in refs],
    )


@pytest.mark.parametrize('ref', ['local://x.nodl.yaml', 'local://a/b.jsonl'])
def test_local_resolver_handles_local_refs(ref):
    assert LocalResolver().handles(ref)


@pytest.mark.parametrize('ref', ['nodl://pkg/x', 'test://x', ''])
def test_local_resolver_ignores_other_schemes(ref):
    assert not LocalResolver().handles(ref)


def test_basic_resolve(tmp_path: Path):
    resolver = LocalResolver()
    relative_path = Path('relative.yaml')
    dest_path = (tmp_path / relative_path).absolute()
    _write(dest_path, NodlDocument())
    resolved_path = resolver.resolve(f'local://{relative_path.name}', dest_path)

    assert resolved_path == (tmp_path / relative_path).absolute()


def test_relative_ref_resolves_against_the_document_directory(tmp_path: Path):
    _write(tmp_path / 'common' / 'pub2.nodl.yaml', _pub_doc('/pub2'))
    doc_path = _write(tmp_path / 'pub1.nodl.yaml', _pub_doc('/pub1', 'local://common/pub2.nodl.yaml'))
    doc = load_nodl(doc_path)
    assert doc.publishers
    assert sorted(p.name for p in doc.publishers) == ['/pub1', '/pub2']


def test_load_from_a_path_supplies_its_own_base(tmp_path: Path):
    _write(tmp_path / 'shared.nodl.yaml', _pub_doc('/shared'))
    root = _write(tmp_path / 'main.nodl.yaml', NodlDocument(include=[Reference(ref='local://shared.nodl.yaml')]))
    doc = load_nodl(root)

    assert doc.publishers
    assert [p.name for p in doc.publishers] == ['/shared']


def test_nested_ref_is_relative_to_its_own_document(tmp_path: Path):
    # b/leaf is named relative to b/mid, not to the top-level document.
    _write(tmp_path / 'b' / 'leaf.nodl.yaml', _pub_doc('/leaf'))
    _write(tmp_path / 'b' / 'mid.nodl.yaml', NodlDocument(include=[Reference(ref='local://leaf.nodl.yaml')]))
    root = _write(tmp_path / 'top.nodl.yaml', NodlDocument(include=[Reference(ref='local://b/mid.nodl.yaml')]))
    doc = load_nodl(root)

    assert doc.publishers
    assert [p.name for p in doc.publishers] == ['/leaf']


def test_relative_ref_may_walk_upward(tmp_path: Path):
    _write(tmp_path / 'shared' / 'base.nodl.yaml', _pub_doc('/base'))
    root = _write(
        tmp_path / 'nodl' / 'node.nodl.yaml', NodlDocument(include=[Reference(ref='local://../shared/base.nodl.yaml')])
    )
    doc = load_nodl(root)

    assert doc.publishers
    assert [p.name for p in doc.publishers] == ['/base']


def test_relative_ref_without_a_base_raises():
    # A local ref has no meaning without a document to resolve it against.
    with pytest.raises(AssertionError):
        LocalResolver().resolve('local://common/telemetry.nodl.yaml', None)


def test_missing_relative_ref_raises(tmp_path: Path):
    root = _write(tmp_path / 'main.nodl.yaml', NodlDocument(include=[Reference(ref='local://absent.nodl.yaml')]))
    with pytest.raises(ResolutionError, match='absent.nodl.yaml'):
        load_nodl(root)


def test_cycle_is_detected_across_spellings(tmp_path: Path):
    # a -> b -> ./a, two spellings of one file.
    _write(tmp_path / 'a.nodl.yaml', NodlDocument(include=[Reference(ref='local://b.nodl.yaml')]))
    _write(tmp_path / 'b.nodl.yaml', NodlDocument(include=[Reference(ref='local://./a.nodl.yaml')]))
    root = tmp_path / 'a.nodl.yaml'
    with pytest.raises(ResolutionError, match='Double-inclusion'):
        load_nodl(root)


def test_double_inclusion_with_different_relative_paths(tmp_path: Path):
    # a -> b -> ./a, two spellings of one file.
    root = tmp_path / 'a.nodl.yaml'
    _write(
        root,
        NodlDocument(
            include=[Reference(ref='local://subdir/b.nodl.yaml'), Reference(ref='local://subdir/c.nodl.yaml')]
        ),
    )
    _write(tmp_path / 'subdir' / 'b.nodl.yaml', NodlDocument(include=[Reference(ref='local://c.nodl.yaml')]))
    _write(tmp_path / 'subdir' / 'c.nodl.yaml', NodlDocument())

    with pytest.raises(ResolutionError, match='Double-inclusion'):
        load_nodl(root)


def test_reference_looping_back_to_the_root_is_detected(tmp_path: Path):
    # Knowing the root's own origin is what makes this catchable at all.
    _write(tmp_path / 'other.nodl.yaml', NodlDocument(include=[Reference(ref='local://root.nodl.yaml')]))
    root = _write(tmp_path / 'root.nodl.yaml', NodlDocument(include=[Reference(ref='local://other.nodl.yaml')]))
    with pytest.raises(ResolutionError, match='Double-inclusion'):
        load_nodl(root)
