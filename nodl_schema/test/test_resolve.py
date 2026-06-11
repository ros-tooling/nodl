# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for nodl_schema.resolve -- no ament_index or live ROS required."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from nodl_schema.models import Interface, Node, ParameterDefinition, QosProfile, TopicEndpoint
from nodl_schema.resolve import resolve

_SYS_QOS = QosProfile(history='SYSTEM_DEFAULT', reliability='SYSTEM_DEFAULT')


def _node(**kwargs) -> Node:
    """Build a Node, defaulting main to an empty document."""
    kwargs.setdefault('main', Interface(nodl_version=2))
    return Node(nodl_version=2, **kwargs)


# ---------------------------------------------------------------------------
# Built-in base resolution
# ---------------------------------------------------------------------------


def test_resolve_no_base_or_mixins():
    layered = resolve(_node())
    assert layered.base is None
    assert layered.mixins == []
    assert layered.merged() == Interface(nodl_version=2)


def test_resolve_base_node_loads_use_sim_time():
    layered = resolve(_node(base='node'))
    assert layered.base is not None
    assert layered.base_name == 'node'
    merged = layered.merged()
    assert merged.parameters is not None
    assert 'use_sim_time' in merged.parameters
    p = merged.parameters['use_sim_time']
    assert (p.type.value if hasattr(p.type, 'value') else p.type) == 'bool'


def test_resolve_base_lifecycle_node_has_use_sim_time():
    merged = resolve(_node(base='lifecycle_node')).merged()
    assert 'use_sim_time' in (merged.parameters or {})


def test_resolve_base_lifecycle_node_has_change_state_service():
    merged = resolve(_node(base='lifecycle_node')).merged()
    names = [s.name for s in (merged.service_servers or [])]
    assert '~/change_state' in names


def test_resolve_base_lifecycle_node_has_transition_event_publisher():
    merged = resolve(_node(base='lifecycle_node')).merged()
    topics = [p.name for p in (merged.publishers or [])]
    assert '~/transition_event' in topics


def test_resolve_unknown_base_raises():
    # Pydantic rejects unknown bases at model construction time.
    with pytest.raises(Exception):
        _node(base='unknown_base')


# ---------------------------------------------------------------------------
# Mixin resolution -- references and in-place documents
# ---------------------------------------------------------------------------


def test_resolve_relative_mixin(tmp_path: Path):
    mixin_file = tmp_path / 'my_mixin.nodl.yaml'
    mixin_file.write_text(
        textwrap.dedent("""\
        nodl_version: 2
        publishers:
          - name: /extra
            type: std_msgs/msg/String
            qos:
              history: SYSTEM_DEFAULT
              reliability: SYSTEM_DEFAULT
    """)
    )

    node = _node(mixins=['my_mixin.nodl.yaml'])
    layered = resolve(node, source_path=tmp_path / 'root.nodl.yaml')
    assert len(layered.mixins) == 1
    topics = [p.name for p in (layered.merged().publishers or [])]
    assert '/extra' in topics


def test_resolve_inplace_mixin_document():
    # The escape hatch: a mixin may be an in-place NoDL document instead of a ref.
    node = _node(
        mixins=[
            Interface(
                nodl_version=2, publishers=[TopicEndpoint(name='/inline', type='std_msgs/msg/String', qos=_SYS_QOS)]
            )
        ]
    )
    merged = resolve(node).merged()
    assert '/inline' in {p.name for p in (merged.publishers or [])}


def test_resolve_relative_mixin_missing_raises(tmp_path: Path):
    node = _node(mixins=['nonexistent.nodl.yaml'])
    with pytest.raises(FileNotFoundError):
        resolve(node, source_path=tmp_path / 'root.nodl.yaml')


def test_resolve_relative_mixin_without_source_raises():
    node = _node(mixins=['./something.nodl.yaml'])
    with pytest.raises(ValueError, match='source path'):
        resolve(node)


def test_resolve_mixin_declaring_composition_keys_rejected(tmp_path: Path):
    # A mixin is validated as an interface definition, which forbids composition
    # keys -- so a referenced file that declares base/main/mixins is rejected.
    mixin = tmp_path / 'bad.nodl.yaml'
    mixin.write_text('nodl_version: 2\nmain:\n  nodl_version: 2\n')
    node = _node(mixins=['bad.nodl.yaml'])
    with pytest.raises(Exception):
        resolve(node, source_path=tmp_path / 'root.nodl.yaml')


# ---------------------------------------------------------------------------
# ResolvedNode.merged() -- layer precedence
# ---------------------------------------------------------------------------


def test_merged_main_wins_over_base():
    """Main document's parameter overrides the base's."""
    node = _node(
        base='node',
        main=Interface(
            nodl_version=2,
            parameters={'use_sim_time': ParameterDefinition(type='bool', default_value=True)},
        ),
    )
    merged = resolve(node).merged()
    # Main sets default_value=True; base has default_value=False
    assert merged.parameters['use_sim_time'].default_value is True


def test_merged_main_wins_over_mixin():
    node = _node(
        main=Interface(
            nodl_version=2,
            parameters={'p': ParameterDefinition(type='int', default_value=2)},
        ),
        mixins=[Interface(nodl_version=2, parameters={'p': ParameterDefinition(type='int', default_value=1)})],
    )
    merged = resolve(node).merged()
    assert merged.parameters['p'].default_value == 2


def test_merged_combines_publishers_from_all_layers(tmp_path: Path):
    mixin_file = tmp_path / 'mixin.nodl.yaml'
    mixin_file.write_text(
        textwrap.dedent("""\
        nodl_version: 2
        publishers:
          - name: /from_mixin
            type: std_msgs/msg/String
            qos:
              history: SYSTEM_DEFAULT
              reliability: SYSTEM_DEFAULT
    """)
    )
    node = _node(
        main=Interface(
            nodl_version=2,
            publishers=[TopicEndpoint(name='/from_main', type='std_msgs/msg/String', qos=_SYS_QOS)],
        ),
        mixins=['mixin.nodl.yaml'],
    )
    merged = resolve(node, source_path=tmp_path / 'root.nodl.yaml').merged()
    topics = {p.name for p in (merged.publishers or [])}
    assert '/from_main' in topics
    assert '/from_mixin' in topics
