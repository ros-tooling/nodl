# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0

from nodl_generator_cpp.provenance import build_provenance_map
from nodl_schema.loader import DocumentTree, IncludedDocument
from nodl_schema.models import (
    ActionEndpoint,
    History,
    NodlDocument,
    QosProfile,
    Reliability,
    ServiceEndpoint,
    TopicEndpoint,
)

_QOS = QosProfile(history=History.SYSTEM_DEFAULT, reliability=Reliability.SYSTEM_DEFAULT)


def _topic(name, type_='std_msgs/msg/String') -> TopicEndpoint:
    return TopicEndpoint(name=name, type=type_, qos=_QOS)


def _service(name, type_='std_srvs/srv/Trigger') -> ServiceEndpoint:
    return ServiceEndpoint(name=name, type=type_)


def _action(name, type_='example_interfaces/action/Fibonacci') -> ActionEndpoint:
    return ActionEndpoint(name=name, type=type_)


def _base_class_codegen(cls='rclcpp::Node', header='rclcpp/rclcpp.hpp'):
    return {'cpp': {'role': 'BASE_CLASS', 'class': cls, 'header': header}}


def _included(ref, doc, children=None):
    return IncludedDocument(ref=ref, doc=doc, resolved_includes=children or [])


def _tree(root, children=None):
    return DocumentTree(root_doc=root, resolved_includes=children or [])


# ---------------------------------------------------------------------------
# No includes
# ---------------------------------------------------------------------------


def test_empty_tree():
    tree = _tree(NodlDocument())
    barriers, entity_map = build_provenance_map(tree)
    assert barriers == []
    assert entity_map == {}


def test_root_entities_not_in_map():
    root = NodlDocument(publishers=[_topic('/status')])
    tree = _tree(root)
    barriers, entity_map = build_provenance_map(tree)
    assert barriers == []
    assert entity_map == {}


# ---------------------------------------------------------------------------
# Single barrier
# ---------------------------------------------------------------------------


def test_single_base_class():
    base_doc = NodlDocument(
        codegen=_base_class_codegen(),
        publishers=[_topic('/rosout')],
    )
    root = NodlDocument(publishers=[_topic('/status')])
    tree = _tree(root, [_included('test://base', base_doc)])

    barriers, entity_map = build_provenance_map(tree)

    assert len(barriers) == 1
    assert barriers[0].class_ == 'rclcpp::Node'
    assert entity_map == {('publishers', '/rosout'): barriers[0]}


def test_all_entity_types_collected():
    base_doc = NodlDocument(
        codegen=_base_class_codegen(),
        publishers=[_topic('/pub')],
        subscriptions=[_topic('/sub')],
        service_servers=[_service('/srv_server')],
        service_clients=[_service('/srv_client')],
        action_servers=[_action('/act_server')],
        action_clients=[_action('/act_client')],
        parameters={'my_param': {'type': 'int', 'default_value': 1}},
    )
    tree = _tree(NodlDocument(), [_included('test://base', base_doc)])

    barriers, entity_map = build_provenance_map(tree)

    assert len(barriers) == 1
    expected_keys = {
        ('publishers', '/pub'),
        ('subscriptions', '/sub'),
        ('service_servers', '/srv_server'),
        ('service_clients', '/srv_client'),
        ('action_servers', '/act_server'),
        ('action_clients', '/act_client'),
        ('parameters', 'my_param'),
    }
    assert set(entity_map.keys()) == expected_keys
    assert all(v is barriers[0] for v in entity_map.values())


# ---------------------------------------------------------------------------
# Inheritance chain (barrier absorbs descendants)
# ---------------------------------------------------------------------------


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
        [
            _included('test://node', node_doc),
        ],
    )
    tree = _tree(NodlDocument(), [lifecycle_inc])

    barriers, entity_map = build_provenance_map(tree)

    assert len(barriers) == 1
    assert barriers[0].class_ == 'rclcpp_lifecycle::LifecycleNode'
    # Both lifecycle's own and node's entities are attributed to lifecycle
    assert ('publishers', '/transition_event') in entity_map
    assert ('publishers', '/rosout') in entity_map
    assert all(v.class_ == 'rclcpp_lifecycle::LifecycleNode' for v in entity_map.values())


# ---------------------------------------------------------------------------
# Non-barrier passthrough
# ---------------------------------------------------------------------------


def test_barrier_grandchild():
    """A plain include wrapping a base-class provider still finds the barrier."""
    base_doc = NodlDocument(
        codegen=_base_class_codegen(),
        publishers=[_topic('/rosout')],
    )
    wrapper_doc = NodlDocument(
        subscriptions=[_topic('/wrapper_sub')],
    )
    wrapper_inc = _included(
        'test://wrapper',
        wrapper_doc,
        [
            _included('test://base', base_doc),
        ],
    )
    tree = _tree(NodlDocument(), [wrapper_inc])

    barriers, entity_map = build_provenance_map(tree)

    assert len(barriers) == 1
    assert barriers[0].class_ == 'rclcpp::Node'
    # Barrier claims its own entities
    assert ('publishers', '/rosout') in entity_map
    # Wrapper's entities are NOT behind a barrier (wrapper has no codegen)
    assert ('subscriptions', '/wrapper_sub') not in entity_map


# ---------------------------------------------------------------------------
# Multiple barriers
# ---------------------------------------------------------------------------


def test_two_sibling_barriers():
    base_a = NodlDocument(
        codegen=_base_class_codegen('A', 'a.hpp'),
        publishers=[_topic('/a_topic')],
    )
    base_b = NodlDocument(
        codegen=_base_class_codegen('B', 'b.hpp'),
        publishers=[_topic('/b_topic')],
    )
    tree = _tree(
        NodlDocument(),
        [
            _included('test://a', base_a),
            _included('test://b', base_b),
        ],
    )

    barriers, entity_map = build_provenance_map(tree)

    assert len(barriers) == 2
    assert ('publishers', '/a_topic') in entity_map
    assert ('publishers', '/b_topic') in entity_map


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

    barriers, entity_map = build_provenance_map(tree)

    assert len(barriers) == 2
