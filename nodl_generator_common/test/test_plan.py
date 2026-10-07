# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Tests for the document tree walk shared by generators."""

from pathlib import Path
from typing import Optional

import pytest
import yaml
from jsonschema import ValidationError

from nodl_generator_common.plan import CodegenPlanner, CodegenSchema, Walk, plan, walk_tree
from nodl_schema.composition import MergeError
from nodl_schema.loader import DocumentTree, IncludedDocument
from nodl_schema.models import History, NodlDocument, QosProfile, Reliability, TopicEndpoint

_QOS = QosProfile(history=History.SYSTEM_DEFAULT, reliability=Reliability.SYSTEM_DEFAULT)


@pytest.fixture
def codegen(tmp_path) -> CodegenSchema[str]:
    """A ``codegen.fake`` schema whose config is a ``role`` string."""
    schema = tmp_path / 'fake.schema.yaml'
    schema.write_text(
        yaml.safe_dump({
            'type': 'object',
            'required': ['role'],
            'additionalProperties': False,
            'properties': {'role': {'enum': ['STOP', 'BAD_PARSE']}},
        })
    )

    def parse(config: dict) -> str:
        if config['role'] == 'BAD_PARSE':
            raise ValidationError('rejected by parse')
        return config['role']

    return CodegenSchema(key='fake', schema=schema, parse=parse)


class RecordingPlanner(CodegenPlanner[str]):
    """Stops at any document with config, and records every visit."""

    def __init__(self) -> None:
        self.root_config: Optional[str] = None
        self.visited: list[str] = []
        self.finalized = False

    def root(self, config: Optional[str]) -> None:
        self.root_config = config

    def visit(self, included: IncludedDocument, config: Optional[str]) -> Walk:
        self.visited.append(included.ref)
        return Walk.CONTINUE if config is None else Walk.STOP

    def finalize(self) -> None:
        self.finalized = True


def _doc(*publishers, role=None):
    return NodlDocument(
        codegen={'fake': {'role': role}} if role else None,
        publishers=[TopicEndpoint(name=name, type='std_msgs/msg/String', qos=_QOS) for name in publishers] or None,
    )


def _included(ref, doc, children=None):
    return IncludedDocument(ref=ref, path=Path(f'{ref}.yaml'), doc=doc, resolved_includes=children or [])


def _publishers(doc):
    return [p.name for p in doc.publishers or []]


# ---------------------------------------------------------------------------
# CodegenSchema.load
# ---------------------------------------------------------------------------


def test_load_absent_config_is_none(codegen):
    assert codegen.load(None) is None
    assert codegen.load({'other': {'role': 'anything'}}) is None


def test_load_validates_and_parses(codegen):
    assert codegen.load({'fake': {'role': 'STOP'}}) == 'STOP'


@pytest.mark.parametrize('config', [{'role': 'UNKNOWN'}, {'role': 'STOP', 'extra': 1}, {'role': 'BAD_PARSE'}])
def test_load_rejects_invalid(codegen, config):
    with pytest.raises(ValidationError):
        codegen.load({'fake': config})


# ---------------------------------------------------------------------------
# walk_tree
# ---------------------------------------------------------------------------


def test_root_is_visited_and_generated(codegen):
    planner = RecordingPlanner()
    doc = walk_tree(DocumentTree(root_doc=_doc('/root', role='STOP'), resolved_includes=[]), codegen, planner)

    assert planner.root_config == 'STOP'
    assert _publishers(doc) == ['/root']


def test_continue_generates_and_walks_into_includes(codegen):
    tree = DocumentTree(
        root_doc=_doc('/root'),
        resolved_includes=[
            _included('a', _doc('/a'), [_included('a1', _doc('/a1'))]),
            _included('b', _doc('/b')),
        ],
    )
    planner = RecordingPlanner()

    doc = walk_tree(tree, codegen, planner)

    assert planner.visited == ['a', 'b', 'a1']
    assert _publishers(doc) == ['/root', '/a', '/b', '/a1']


def test_stop_neither_generates_nor_walks_into_includes(codegen):
    tree = DocumentTree(
        root_doc=_doc('/root'),
        resolved_includes=[
            _included('provider', _doc('/provided', role='STOP'), [_included('behind', _doc('/behind'))])
        ],
    )
    planner = RecordingPlanner()

    doc = walk_tree(tree, codegen, planner)

    assert planner.visited == ['provider']
    assert _publishers(doc) == ['/root']


def test_invalid_config_raises_during_walk(codegen):
    tree = DocumentTree(root_doc=_doc(), resolved_includes=[_included('bad', _doc(role='BAD_PARSE'))])
    with pytest.raises(ValidationError, match='rejected by parse'):
        walk_tree(tree, codegen, RecordingPlanner())


# ---------------------------------------------------------------------------
# plan
# ---------------------------------------------------------------------------


def _write(path: Path, content: dict) -> Path:
    path.write_text(yaml.safe_dump({'nodl_version': 2, **content}))
    return path


_PUBLISHER = {'type': 'std_msgs/msg/String', 'qos': {'history': 'SYSTEM_DEFAULT', 'reliability': 'SYSTEM_DEFAULT'}}


def test_plan_returns_doc_and_sources_and_finalizes_planner(tmp_path, codegen):
    provider = _write(tmp_path / 'provider.nodl.yaml', {'codegen': {'fake': {'role': 'STOP'}}})
    root = _write(
        tmp_path / 'root.nodl.yaml',
        {'include': [{'ref': 'local://provider.nodl.yaml'}], 'publishers': [{'name': '/root', **_PUBLISHER}]},
    )

    planner = RecordingPlanner()
    planned = plan(root, codegen, planner)

    assert _publishers(planned.doc) == ['/root']
    assert planned.sources == [root.resolve(), provider.resolve()]
    assert planner.visited == ['local://provider.nodl.yaml']
    assert planner.finalized


def test_plan_reports_collisions_in_documents_that_are_not_generated(tmp_path, codegen):
    _write(
        tmp_path / 'provider.nodl.yaml',
        {'codegen': {'fake': {'role': 'STOP'}}, 'publishers': [{'name': '/same', **_PUBLISHER}]},
    )
    root = _write(
        tmp_path / 'root.nodl.yaml',
        {'include': [{'ref': 'local://provider.nodl.yaml'}], 'publishers': [{'name': '/same', **_PUBLISHER}]},
    )

    with pytest.raises(MergeError, match='/same'):
        plan(root, codegen, RecordingPlanner())
