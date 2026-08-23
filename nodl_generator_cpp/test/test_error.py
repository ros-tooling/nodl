# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0

"""Error-path tests for nodl_generator_cpp.

Tests that ``generate_cpp`` rejects invalid inputs with the correct
exception types.  Provenance and codegen-semantic errors raise
:class:`CodegenError`; upstream schema/resolution errors propagate
unchanged; bad ``target_name`` values raise :class:`ValueError`.

Document-construction helpers follow the same pattern as
``nodl_schema/test/test_composition.py``.
"""

import pytest

from nodl_generator_cpp.generate import CodegenError, generate_cpp
from nodl_schema import dump_nodl
from nodl_schema.models import (
    History,
    NodlDocument,
    QosProfile,
    Reference,
    Reliability,
    TopicEndpoint,
)

_QOS = QosProfile(history=History.SYSTEM_DEFAULT, reliability=Reliability.SYSTEM_DEFAULT)


def _topic(name, type_='std_msgs/msg/String') -> TopicEndpoint:
    return TopicEndpoint(name=name, type=type_, qos=_QOS)


def _refs(*refs) -> list[Reference]:
    return [Reference(ref=ref) for ref in refs]


def _including(*refs) -> NodlDocument:
    """A document whose only content is what it includes."""
    return NodlDocument(include=_refs(*refs))


def _base_class_codegen(cls='rclcpp::Node', header='rclcpp/rclcpp.hpp'):
    """The ``codegen`` dict for a ``BASE_CLASS`` provider."""
    return {'cpp': {'role': 'BASE_CLASS', 'class': cls, 'header': header}}


def _base_class_doc(cls='rclcpp::Node', header='rclcpp/rclcpp.hpp', *refs, topic='/provided'):
    """A document that declares itself as a ``base_class`` provider."""
    return NodlDocument(
        codegen=_base_class_codegen(cls, header),
        publishers=[_topic(topic)],
        include=_refs(*refs) or None,
    )


def _write_nodl(tmp_path, doc, name='root.nodl.yaml'):
    """Write a NodlDocument to a temp file and return its Path."""
    path = tmp_path / name
    path.write_text(dump_nodl(doc))
    return path


_TARGET = 'my_node'


# ---------------------------------------------------------------------------
# Provenance errors (CodegenError)
# ---------------------------------------------------------------------------


def test_two_sibling_base_class_includes(fake_resolver, tmp_path):
    ref_a = fake_resolver.add('base_a', _base_class_doc('A', 'a.hpp', topic='/provided_a'))
    ref_b = fake_resolver.add('base_b', _base_class_doc('B', 'b.hpp', topic='/provided_b'))
    root = NodlDocument(
        publishers=[_topic('/my_topic')],
        include=_refs(ref_a, ref_b),
    )
    with pytest.raises(CodegenError, match='[Cc]onflict|[Mm]ultiple.*base class'):
        generate_cpp(_write_nodl(tmp_path, root), _TARGET)


def test_two_sibling_base_class_includes_same_class_still_errors(fake_resolver, tmp_path):
    ref_a = fake_resolver.add('base_a', _base_class_doc('rclcpp::Node', 'rclcpp/rclcpp.hpp', topic='/provided_a'))
    ref_b = fake_resolver.add('base_b', _base_class_doc('rclcpp::Node', 'rclcpp/rclcpp.hpp', topic='/provided_b'))
    root = NodlDocument(
        publishers=[_topic('/my_topic')],
        include=_refs(ref_a, ref_b),
    )
    with pytest.raises(CodegenError, match='[Cc]onflict|[Mm]ultiple.*base class'):
        generate_cpp(_write_nodl(tmp_path, root), _TARGET)


def test_no_base_class_fails(fake_resolver, tmp_path):
    root = NodlDocument(publishers=[_topic('/my_topic')])
    with pytest.raises(CodegenError, match='[Nn]o base class'):
        generate_cpp(_write_nodl(tmp_path, root), _TARGET)


def test_no_base_class_with_include_fails(fake_resolver, tmp_path):
    ref = fake_resolver.add('plain', NodlDocument(publishers=[_topic('/extra')]))
    root = NodlDocument(
        publishers=[_topic('/my_topic')],
        include=_refs(ref),
    )
    with pytest.raises(CodegenError, match='[Nn]o base class'):
        generate_cpp(_write_nodl(tmp_path, root), _TARGET)


# ---------------------------------------------------------------------------
# target_name validation (ValueError)
# ---------------------------------------------------------------------------


def test_empty_target_name(fake_resolver, tmp_path):
    """generate_cpp rejects an empty target name."""
    root = NodlDocument(
        include=_refs('test://rclcpp_node'),
        publishers=[_topic('/my_topic')],
    )
    with pytest.raises(ValueError, match='target_name'):
        generate_cpp(_write_nodl(tmp_path, root), '')


def test_non_identifier_target_name(fake_resolver, tmp_path):
    """generate_cpp rejects a non-identifier target name."""
    root = NodlDocument(
        include=_refs('test://rclcpp_node'),
        publishers=[_topic('/my_topic')],
    )
    with pytest.raises(ValueError, match='target_name'):
        generate_cpp(_write_nodl(tmp_path, root), '123bad')


def test_target_name_with_spaces(fake_resolver, tmp_path):
    """generate_cpp rejects a target name containing spaces."""
    root = NodlDocument(
        include=_refs('test://rclcpp_node'),
        publishers=[_topic('/my_topic')],
    )
    with pytest.raises(ValueError, match='target_name'):
        generate_cpp(_write_nodl(tmp_path, root), 'has space')
