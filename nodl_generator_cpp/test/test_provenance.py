# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""C++ adapter tests over the shared provenance core.

The generic barrier-walk behaviour is tested in
``nodl_generator_common``; these tests cover the ``codegen_cpp`` adapter
and its integration with the real :class:`CodegenCpp` model.
"""

from pathlib import Path

from nodl_generator_common.provenance import build_provenance_map
from nodl_generator_cpp.provenance import codegen_cpp
from nodl_schema.loader import DocumentTree, IncludedDocument
from nodl_schema.models import History, NodlDocument, QosProfile, Reliability, TopicEndpoint

_QOS = QosProfile(history=History.SYSTEM_DEFAULT, reliability=Reliability.SYSTEM_DEFAULT)


def _topic(name, type_='std_msgs/msg/String') -> TopicEndpoint:
    return TopicEndpoint(name=name, type=type_, qos=_QOS)


def _base_class_codegen(cls='rclcpp::Node', header='rclcpp/rclcpp.hpp'):
    return {'cpp': {'role': 'BASE_CLASS', 'class': cls, 'header': header}}


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
