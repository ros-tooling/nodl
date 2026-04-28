"""Unit tests for nodl.resolve — no ament_index or live ROS required."""
from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from nodl.models import FragmentRef, NodlDocument, Parameter, QoS, ServiceEndpoint, TopicEndpoint
from nodl.resolve import LayeredDocument, resolve

_SYS_QOS = QoS(history='SYSTEM_DEFAULT', reliability='SYSTEM_DEFAULT')
_FRAG_HEADER = 'nodl_version: 2\n'


# ---------------------------------------------------------------------------
# Built-in base resolution
# ---------------------------------------------------------------------------

def test_resolve_no_base_or_fragments():
    doc = NodlDocument(nodl_version=2)
    layered = resolve(doc)
    assert layered.base is None
    assert layered.fragments == {}
    assert layered.merged() == NodlDocument(nodl_version=2)


def test_resolve_base_node_loads_use_sim_time():
    doc = NodlDocument(nodl_version=2, base='node')
    layered = resolve(doc)
    assert layered.base is not None
    assert layered.base_name == 'node'
    merged = layered.merged()
    assert merged.parameters is not None
    assert 'use_sim_time' in merged.parameters
    assert merged.parameters['use_sim_time'].type == 'bool'


def test_resolve_base_lifecycle_node_has_use_sim_time():
    doc = NodlDocument(nodl_version=2, base='lifecycle_node')
    layered = resolve(doc)
    merged = layered.merged()
    assert 'use_sim_time' in (merged.parameters or {})


def test_resolve_base_lifecycle_node_has_change_state_service():
    doc = NodlDocument(nodl_version=2, base='lifecycle_node')
    layered = resolve(doc)
    merged = layered.merged()
    names = [s.name for s in (merged.service_servers or [])]
    assert '~/change_state' in names


def test_resolve_base_lifecycle_node_has_transition_event_publisher():
    doc = NodlDocument(nodl_version=2, base='lifecycle_node')
    layered = resolve(doc)
    merged = layered.merged()
    topics = [p.name for p in (merged.publishers or [])]
    assert '~/transition_event' in topics


def test_resolve_unknown_base_raises():
    # Pydantic rejects unknown bases at model construction time.
    with pytest.raises(Exception):
        NodlDocument(nodl_version=2, base='unknown_base')  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Fragment resolution — relative path
# ---------------------------------------------------------------------------

def test_resolve_relative_fragment(tmp_path: Path):
    frag_file = tmp_path / 'my_frag.nodl.yaml'
    frag_file.write_text(textwrap.dedent("""\
        nodl_version: 2
        publishers:
          - name: /extra
            type: std_msgs/msg/String
            qos:
              history: SYSTEM_DEFAULT
              reliability: SYSTEM_DEFAULT
    """))

    doc = NodlDocument(
        nodl_version=2,
        fragments=[FragmentRef(ref='my_frag.nodl.yaml', name='extra')],
    )
    layered = resolve(doc, source_path=tmp_path / 'root.nodl.yaml')
    assert 'extra' in layered.fragments
    merged = layered.merged()
    topics = [p.name for p in (merged.publishers or [])]
    assert '/extra' in topics


def test_resolve_relative_fragment_missing_raises(tmp_path: Path):
    doc = NodlDocument(nodl_version=2, fragments=[FragmentRef(ref='nonexistent.nodl.yaml')])
    with pytest.raises(FileNotFoundError):
        resolve(doc, source_path=tmp_path / 'root.nodl.yaml')


def test_resolve_relative_fragment_without_source_raises():
    doc = NodlDocument(nodl_version=2, fragments=[FragmentRef(ref='./something.nodl.yaml')])
    with pytest.raises(ValueError, match='source path'):
        resolve(doc)


# ---------------------------------------------------------------------------
# LayeredDocument.merged() — layer precedence
# ---------------------------------------------------------------------------

def test_merged_main_wins_over_base():
    """Main document's parameter overrides the base's."""
    doc = NodlDocument(
        nodl_version=2,
        base='node',
        parameters={'use_sim_time': Parameter(type='bool', default_value=True)},
    )
    layered = resolve(doc)
    merged = layered.merged()
    # Main sets default_value=True; base has default_value=False
    assert merged.parameters['use_sim_time'].default_value is True


def test_merged_fragment_wins_over_base(tmp_path: Path):
    frag_file = tmp_path / 'frag.nodl.yaml'
    frag_file.write_text(textwrap.dedent("""\
        nodl_version: 2
        parameters:
          use_sim_time:
            type: bool
            default_value: true
    """))
    doc = NodlDocument(
        nodl_version=2,
        base='node',
        fragments=[FragmentRef(ref='frag.nodl.yaml', name='frag')],
    )
    layered = resolve(doc, source_path=tmp_path / 'root.nodl.yaml')
    merged = layered.merged()
    assert merged.parameters['use_sim_time'].default_value is True


def test_merged_combines_publishers_from_all_layers(tmp_path: Path):
    frag_file = tmp_path / 'frag.nodl.yaml'
    frag_file.write_text(textwrap.dedent("""\
        nodl_version: 2
        publishers:
          - name: /from_frag
            type: std_msgs/msg/String
            qos:
              history: SYSTEM_DEFAULT
              reliability: SYSTEM_DEFAULT
    """))
    doc = NodlDocument(
        nodl_version=2,
        publishers=[TopicEndpoint(name='/from_main', type='std_msgs/msg/String', qos=_SYS_QOS)],
        fragments=[FragmentRef(ref='frag.nodl.yaml', name='f')],
    )
    layered = resolve(doc, source_path=tmp_path / 'root.nodl.yaml')
    merged = layered.merged()
    topics = {p.name for p in (merged.publishers or [])}
    assert '/from_main' in topics
    assert '/from_frag' in topics


def test_fragment_label_defaults_to_ref(tmp_path: Path):
    frag_file = tmp_path / 'f.nodl.yaml'
    frag_file.write_text(textwrap.dedent("""\
        nodl_version: 2
        publishers:
          - name: /t
            type: std_msgs/msg/String
            qos:
              history: SYSTEM_DEFAULT
              reliability: SYSTEM_DEFAULT
    """))
    doc = NodlDocument(nodl_version=2, fragments=[FragmentRef(ref='f.nodl.yaml')])
    layered = resolve(doc, source_path=tmp_path / 'root.nodl.yaml')
    assert 'f.nodl.yaml' in layered.fragments
