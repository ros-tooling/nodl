# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""C++ adapter tests over the shared provenance core.

The generic barrier-walk behaviour is tested in
``nodl_generator_common``; these tests cover the ``codegen_cpp`` adapter
and its integration with the real :class:`CodegenCpp` model.
"""

from pathlib import Path

import pytest

from nodl_generator_common.provenance import build_provenance_map
from nodl_generator_cpp.generate import CodegenError, cmake_deps, generate_cpp
from nodl_generator_cpp.provenance import codegen_cpp
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


# ---------------------------------------------------------------------------
# codegen_cpp adapter
# ---------------------------------------------------------------------------


def test_codegen_cpp_none_without_metadata():
    assert codegen_cpp(NodlDocument()) is None


def test_codegen_cpp_parses_metadata():
    doc = NodlDocument(codegen=_base_class_codegen())
    config = codegen_cpp(doc)
    assert config is not None
    assert config.class_ == 'rclcpp::Node'
    assert config.header == 'rclcpp/rclcpp.hpp'


# ---------------------------------------------------------------------------
# Integration with build_provenance_map + the real CodegenCpp model
# ---------------------------------------------------------------------------


def test_single_base_class():
    base_doc = NodlDocument(
        codegen=_base_class_codegen(),
        publishers=[_topic('/rosout')],
    )
    root = NodlDocument(publishers=[_topic('/status')])
    tree = _tree(root, [_included('test://base', base_doc)])

    barriers, entity_map = build_provenance_map(tree, codegen_cpp)

    assert len(barriers) == 1
    assert barriers[0].class_ == 'rclcpp::Node'
    assert entity_map == {('publishers', '/rosout'): barriers[0]}


def test_chain_produces_single_barrier():
    """LifecycleNode includes Node — only LifecycleNode is a barrier."""
    node_doc = NodlDocument(
        codegen=_base_class_codegen('rclcpp::Node', 'rclcpp/rclcpp.hpp'),
        publishers=[_topic('/rosout')],
    )
    lifecycle_doc = NodlDocument(
        codegen=_base_class_codegen(
            'rclcpp_lifecycle::LifecycleNode',
            'rclcpp_lifecycle/lifecycle_node.hpp',
        ),
        publishers=[_topic('/transition_event')],
    )
    lifecycle_inc = _included(
        'test://lifecycle',
        lifecycle_doc,
        [_included('test://node', node_doc)],
    )
    tree = _tree(NodlDocument(), [lifecycle_inc])

    barriers, entity_map = build_provenance_map(tree, codegen_cpp)

    assert len(barriers) == 1
    assert barriers[0].class_ == 'rclcpp_lifecycle::LifecycleNode'
    assert ('publishers', '/transition_event') in entity_map
    assert ('publishers', '/rosout') in entity_map
    assert all(v.class_ == 'rclcpp_lifecycle::LifecycleNode' for v in entity_map.values())


def test_duplicate_class_still_two_barriers():
    base_a = NodlDocument(
        codegen=_base_class_codegen('rclcpp::Node', 'rclcpp/rclcpp.hpp'),
        publishers=[_topic('/a_topic')],
    )
    base_b = NodlDocument(
        codegen=_base_class_codegen('rclcpp::Node', 'rclcpp/rclcpp.hpp'),
        publishers=[_topic('/b_topic')],
    )
    tree = _tree(
        NodlDocument(),
        [
            _included('test://a', base_a),
            _included('test://b', base_b),
        ],
    )

    barriers, entity_map = build_provenance_map(tree, codegen_cpp)

    assert len(barriers) == 2


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
