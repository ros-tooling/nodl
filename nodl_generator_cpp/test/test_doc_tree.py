# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Tests for how the C++ generator walks the document tree.

``_plan_tree`` splits the tree into base classes and the merged document the generator owns.
"""

from pathlib import Path

import pytest

from nodl_generator_cpp.generate import CodegenError, _plan_tree, cmake_deps, generate_cpp
from nodl_schema import dump_nodl
from nodl_schema.loader import DocumentTree, IncludedDocument
from nodl_schema.models import History, NodlDocument, QosProfile, Reference, Reliability, TopicEndpoint

_QOS = QosProfile(history=History.SYSTEM_DEFAULT, reliability=Reliability.SYSTEM_DEFAULT)


def _topic(name, type_='std_msgs/msg/String') -> TopicEndpoint:
    return TopicEndpoint(name=name, type=type_, qos=_QOS)


def _base_class_codegen(cls='rclcpp::Node', header='rclcpp/rclcpp.hpp'):
    return {'cpp': {'role': 'BASE_CLASS', 'class': cls, 'header': header}}


def _no_generate_codegen():
    return {'cpp': {'role': 'NO_GENERATE'}}


def _included(ref, doc, children=None):
    path = Path(f'{ref.lstrip("test://")}.yaml')
    return IncludedDocument(ref=ref, path=path, doc=doc, resolved_includes=children or [])


def _tree(root, children=None):
    return DocumentTree(root_doc=root, resolved_includes=children or [])


def _publishers(doc):
    return [p.name for p in doc.publishers or []]


# ---------------------------------------------------------------------------
# _plan_tree
# ---------------------------------------------------------------------------


def test_root_only():
    bases, doc = _plan_tree(_tree(NodlDocument(publishers=[_topic('/status')])))
    assert bases == []
    assert _publishers(doc) == ['/status']


def test_base_class_is_selected_and_not_owned():
    base_doc = NodlDocument(codegen=_base_class_codegen(), publishers=[_topic('/rosout')])
    root = NodlDocument(publishers=[_topic('/status')])

    bases, doc = _plan_tree(_tree(root, [_included('test://base', base_doc)]))

    assert [b.class_ for b in bases] == ['rclcpp::Node']
    assert _publishers(doc) == ['/status']


def test_walk_does_not_descend_into_base_class():
    """LifecycleNode includes Node, and only LifecycleNode is a base."""
    node_doc = NodlDocument(codegen=_base_class_codegen(), publishers=[_topic('/rosout')])
    lifecycle_doc = NodlDocument(
        codegen=_base_class_codegen('rclcpp_lifecycle::LifecycleNode', 'rclcpp_lifecycle/lifecycle_node.hpp'),
        publishers=[_topic('/transition_event')],
    )
    tree = _tree(
        NodlDocument(),
        [_included('test://lifecycle', lifecycle_doc, [_included('test://node', node_doc)])],
    )

    bases, doc = _plan_tree(tree)

    assert [b.class_ for b in bases] == ['rclcpp_lifecycle::LifecycleNode']
    assert _publishers(doc) == []


def test_document_without_codegen_is_owned_and_walked_into():
    base_doc = NodlDocument(codegen=_base_class_codegen(), publishers=[_topic('/rosout')])
    plain_doc = NodlDocument(publishers=[_topic('/plain')])
    tree = _tree(
        NodlDocument(publishers=[_topic('/status')]),
        [_included('test://plain', plain_doc, [_included('test://base', base_doc)])],
    )

    bases, doc = _plan_tree(tree)

    assert [b.class_ for b in bases] == ['rclcpp::Node']
    assert _publishers(doc) == ['/status', '/plain']


def test_no_generate_is_neither_owned_nor_a_base():
    ignored = NodlDocument(codegen=_no_generate_codegen(), publishers=[_topic('/ignored')])
    tree = _tree(NodlDocument(publishers=[_topic('/status')]), [_included('test://ignored', ignored)])

    bases, doc = _plan_tree(tree)

    assert bases == []
    assert _publishers(doc) == ['/status']


def test_two_base_classes_are_both_returned():
    tree = _tree(
        NodlDocument(),
        [
            _included('test://a', NodlDocument(codegen=_base_class_codegen())),
            _included('test://b', NodlDocument(codegen=_base_class_codegen())),
        ],
    )

    bases, _ = _plan_tree(tree)

    assert len(bases) == 2


# ---------------------------------------------------------------------------
# End to end
# ---------------------------------------------------------------------------


def test_no_generate_filters_entities_without_selecting_base(fake_resolver, tmp_path):
    ignored_ref = fake_resolver.add(
        'ignored',
        NodlDocument(
            codegen=_no_generate_codegen(),
            publishers=[_topic('/ignored', 'sensor_msgs/msg/Image')],
        ),
    )
    root = NodlDocument(
        include=[Reference(ref='test://rclcpp_node'), Reference(ref=ignored_ref)],
        publishers=[_topic('/status')],
    )
    source = tmp_path / 'root.nodl.yaml'
    source.write_text(dump_nodl(root))

    generated = generate_cpp(source, 'my_node_base')
    content = '\n'.join(file.content for file in generated)
    dependencies = cmake_deps(source, 'my_node_base')

    assert '/status' in content
    assert '/ignored' not in content
    assert fake_resolver.docs[ignored_ref].resolve() in dependencies.sources
    assert 'sensor_msgs' not in dependencies.ros_deps
    assert 'rclcpp' in dependencies.ros_deps


def test_no_generate_hides_transitive_base_class(fake_resolver, tmp_path):
    ignored_ref = fake_resolver.add(
        'ignored_wrapper',
        NodlDocument(
            codegen=_no_generate_codegen(),
            include=[Reference(ref='test://rclcpp_node')],
        ),
    )
    root = NodlDocument(include=[Reference(ref=ignored_ref)])
    source = tmp_path / 'root.nodl.yaml'
    source.write_text(dump_nodl(root))

    with pytest.raises(CodegenError, match='No base class'):
        generate_cpp(source, 'my_node_base')
