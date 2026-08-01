# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Integration tests for NoDL include resolution via the ament index.

These tests require the embedded test workspace to be built (handled
automatically by the ``test_ws_env`` session fixture in conftest.py).
"""

from __future__ import annotations

import json
import subprocess
import sys
import textwrap
from pathlib import Path

import yaml


def _write_yaml(path: Path, data: dict) -> None:
    """Write a dict as YAML to *path*, creating parent dirs."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.dump(data, default_flow_style=False), encoding='utf-8')


def _load_nodl_subprocess(env: dict[str, str], nodl_file: Path) -> dict:
    """Run ``load_nodl`` in a subprocess with the given environment.

    Returns the resulting ``NodlDocument`` serialized as a plain dict.
    Raises ``AssertionError`` (with stderr) on non-zero exit.
    """
    script = textwrap.dedent(f"""\
        import json
        from pathlib import Path
        from nodl_schema import load_nodl
        doc = load_nodl(Path({str(nodl_file)!r}))
        print(json.dumps(json.loads(doc.json(exclude_none=True))))
    """)
    result = subprocess.run(
        [sys.executable, '-c', script],
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 0, f'load_nodl failed:\n{result.stderr}'
    return json.loads(result.stdout)


def _load_nodl_subprocess_error(env: dict[str, str], nodl_file: Path) -> str:
    """Run ``load_nodl`` in a subprocess expecting failure.

    Returns the stderr output.  Asserts that the process exits non-zero.
    """
    script = textwrap.dedent(f"""\
        from pathlib import Path
        from nodl_schema import load_nodl
        load_nodl(Path({str(nodl_file)!r}))
    """)
    result = subprocess.run(
        [sys.executable, '-c', script],
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode != 0, f'Expected failure but got success:\n{result.stdout}'
    return result.stderr


def test_test_ws_env_has_test_packages(test_ws_env):
    """Smoke test: the test workspace env includes our fragment packages."""
    ament_prefix_path = test_ws_env.get('AMENT_PREFIX_PATH', '')
    assert 'nodl_fragment_a' in ament_prefix_path
    assert 'nodl_fragment_b' in ament_prefix_path


def test_nodl_files_installed(test_ws_env):
    """Smoke test: NoDL files are actually installed in the test workspace."""
    ament_prefix_path = test_ws_env['AMENT_PREFIX_PATH']
    prefixes = ament_prefix_path.split(':')

    # Find the nodl_fragment_a prefix
    frag_a_prefix = next((p for p in prefixes if 'nodl_fragment_a' in p), None)
    assert frag_a_prefix is not None, f'nodl_fragment_a not in AMENT_PREFIX_PATH: {ament_prefix_path}'

    nodl_dir = Path(frag_a_prefix) / 'share' / 'nodl_fragment_a' / 'nodl'
    assert nodl_dir.is_dir(), f'NoDL directory not found: {nodl_dir}'
    assert (nodl_dir / 'diagnostics.nodl.yaml').is_file()
    assert (nodl_dir / 'shared_base.nodl.yaml').is_file()


# ---------------------------------------------------------------------------
# load_nodl() resolves package URIs via the ament index
# ---------------------------------------------------------------------------


def test_load_nodl_resolves_package_uri(test_ws_env, tmp_path):
    """A file with a nodl:// include resolves and merges the fragment's interface."""
    main_file = tmp_path / 'main.nodl.yaml'
    _write_yaml(
        main_file,
        {
            'nodl_version': 2,
            'includes': [{'ref': 'nodl://nodl_fragment_a/diagnostics'}],
        },
    )
    doc = _load_nodl_subprocess(test_ws_env, main_file)
    # nodl_fragment_a/diagnostics.nodl.yaml declares a /diagnostics publisher
    pub_names = [p['name'] for p in doc.get('publishers', [])]
    assert '/diagnostics' in pub_names


def test_load_nodl_cross_package_merge(test_ws_env, tmp_path):
    """Includes from both nodl_fragment_a and nodl_fragment_b merge their interfaces."""
    main_file = tmp_path / 'main.nodl.yaml'
    _write_yaml(
        main_file,
        {
            'nodl_version': 2,
            'includes': [
                {'ref': 'nodl://nodl_fragment_a/diagnostics'},
                {'ref': 'nodl://nodl_fragment_a/shared_base'},
                {'ref': 'nodl://nodl_fragment_b/sensors'},
            ],
        },
    )
    doc = _load_nodl_subprocess(test_ws_env, main_file)

    # diagnostics fragment: /diagnostics publisher
    pub_names = [p['name'] for p in doc.get('publishers', [])]
    assert '/diagnostics' in pub_names

    # sensors fragment: /sensor_data publisher
    assert '/sensor_data' in pub_names

    # shared_base fragment: use_sim_time parameter
    assert 'use_sim_time' in doc.get('parameters', {})


def test_load_nodl_package_uri_not_found_error(test_ws_env, tmp_path):
    """nodl://nonexistent_pkg/x → clear error message."""
    main_file = tmp_path / 'main.nodl.yaml'
    _write_yaml(
        main_file,
        {
            'nodl_version': 2,
            'includes': [{'ref': 'nodl://nonexistent_pkg/x'}],
        },
    )
    stderr = _load_nodl_subprocess_error(test_ws_env, main_file)
    assert 'PackageNotFoundError' in stderr
    assert 'nonexistent_pkg' in stderr


def test_load_nodl_package_file_not_found_error(test_ws_env, tmp_path):
    """nodl://nodl_fragment_a/no_such_file → clear error."""
    main_file = tmp_path / 'main.nodl.yaml'
    _write_yaml(
        main_file,
        {
            'nodl_version': 2,
            'includes': [{'ref': 'nodl://nodl_fragment_a/no_such_file'}],
        },
    )
    stderr = _load_nodl_subprocess_error(test_ws_env, main_file)
    assert 'FileNotFoundError' in stderr
    assert 'no_such_file' in stderr


# ---------------------------------------------------------------------------
# load_nodl() include merge semantics
# ---------------------------------------------------------------------------

_MIN_QOS = {'history': 'SYSTEM_DEFAULT', 'reliability': 'SYSTEM_DEFAULT'}


def test_load_nodl_include_merges_publishers(test_ws_env, tmp_path):
    """A file with a nodl:// include merges the fragment's publishers."""
    main_file = tmp_path / 'main.nodl.yaml'
    _write_yaml(
        main_file,
        {
            'nodl_version': 2,
            'includes': [{'ref': 'nodl://nodl_fragment_a/topic_a'}],
        },
    )
    doc = _load_nodl_subprocess(test_ws_env, main_file)
    pub_names = [p['name'] for p in doc.get('publishers', [])]
    assert '/topic_a' in pub_names


def test_load_nodl_include_merges_all_sections(test_ws_env, tmp_path):
    """Parameters, publishers, subscriptions, service and action endpoints all merge."""
    main_file = tmp_path / 'main.nodl.yaml'
    _write_yaml(
        main_file,
        {
            'nodl_version': 2,
            'includes': [{'ref': 'nodl://nodl_fragment_a/all_endpoints'}],
        },
    )
    doc = _load_nodl_subprocess(test_ws_env, main_file)
    assert 'speed' in doc.get('parameters', {})
    assert any(p['name'] == '/topic_a' for p in doc.get('publishers', []))
    assert any(s['name'] == '/sub_a' for s in doc.get('subscriptions', []))
    assert any(s['name'] == '/set_bool' for s in doc.get('service_servers', []))
    assert any(s['name'] == '/trigger' for s in doc.get('service_clients', []))
    assert any(a['name'] == '/navigate' for a in doc.get('action_servers', []))
    assert any(a['name'] == '/spin' for a in doc.get('action_clients', []))


def test_load_nodl_local_declaration_wins_over_include(test_ws_env, tmp_path):
    """Same-name topic declared locally and in include → local declaration wins."""
    main_file = tmp_path / 'main.nodl.yaml'
    _write_yaml(
        main_file,
        {
            'nodl_version': 2,
            'includes': [{'ref': 'nodl://nodl_fragment_a/topic_a_twist'}],
            'publishers': [
                {
                    'name': '/topic_a',
                    'type': 'std_msgs/msg/String',
                    'qos': _MIN_QOS,
                }
            ],
        },
    )
    doc = _load_nodl_subprocess(test_ws_env, main_file)
    pubs = [p for p in doc.get('publishers', []) if p['name'] == '/topic_a']
    assert len(pubs) == 1
    assert pubs[0]['type'] == 'std_msgs/msg/String'


def test_load_nodl_diamond_deduplication(test_ws_env, tmp_path):
    """A→B, A→C, B→D, C→D: D's interface appears exactly once."""
    main_file = tmp_path / 'main.nodl.yaml'
    _write_yaml(
        main_file,
        {
            'nodl_version': 2,
            'includes': [
                {'ref': 'nodl://nodl_fragment_a/wraps_topic_a'},
                {'ref': 'nodl://nodl_fragment_b/wraps_topic_a'},
            ],
        },
    )
    doc = _load_nodl_subprocess(test_ws_env, main_file)
    pubs = [p for p in doc.get('publishers', []) if p['name'] == '/topic_a']
    assert len(pubs) == 1


def test_load_nodl_merge_identical_ok(test_ws_env, tmp_path):
    """Two includes declare same topic identically → deduplicated silently."""
    main_file = tmp_path / 'main.nodl.yaml'
    _write_yaml(
        main_file,
        {
            'nodl_version': 2,
            'includes': [
                {'ref': 'nodl://nodl_fragment_a/topic_a'},
                {'ref': 'nodl://nodl_fragment_b/topic_a'},
            ],
        },
    )
    doc = _load_nodl_subprocess(test_ws_env, main_file)
    pubs = [p for p in doc.get('publishers', []) if p['name'] == '/topic_a']
    assert len(pubs) == 1


def test_load_nodl_merge_conflict_error(test_ws_env, tmp_path):
    """Two includes declare same topic with different type → error."""
    main_file = tmp_path / 'main.nodl.yaml'
    _write_yaml(
        main_file,
        {
            'nodl_version': 2,
            'includes': [
                {'ref': 'nodl://nodl_fragment_a/topic_a'},
                {'ref': 'nodl://nodl_fragment_a/topic_a_twist'},
            ],
        },
    )
    stderr = _load_nodl_subprocess_error(test_ws_env, main_file)
    assert 'topic_a' in stderr


# ---------------------------------------------------------------------------
# Merge-if-identical across all section types
# ---------------------------------------------------------------------------


def test_merge_identical_all_sections_ok(test_ws_env, tmp_path):
    """Two includes with identical endpoints across all section types → deduplicated."""
    main_file = tmp_path / 'main.nodl.yaml'
    _write_yaml(
        main_file,
        {
            'nodl_version': 2,
            'includes': [
                {'ref': 'nodl://nodl_fragment_a/all_endpoints'},
                {'ref': 'nodl://nodl_fragment_b/all_endpoints'},
            ],
        },
    )
    doc = _load_nodl_subprocess(test_ws_env, main_file)
    assert len([p for p in doc.get('publishers', []) if p['name'] == '/topic_a']) == 1
    assert len([s for s in doc.get('subscriptions', []) if s['name'] == '/sub_a']) == 1
    assert len([s for s in doc.get('service_servers', []) if s['name'] == '/set_bool']) == 1
    assert len([s for s in doc.get('service_clients', []) if s['name'] == '/trigger']) == 1
    assert len([a for a in doc.get('action_servers', []) if a['name'] == '/navigate']) == 1
    assert len([a for a in doc.get('action_clients', []) if a['name'] == '/spin']) == 1
    assert 'speed' in doc.get('parameters', {})


# ---------------------------------------------------------------------------
# Merge-conflict across all section types
# ---------------------------------------------------------------------------


def test_merge_conflict_subscriptions(test_ws_env, tmp_path):
    """Two includes declare same subscription with different type → error."""
    main_file = tmp_path / 'main.nodl.yaml'
    _write_yaml(
        main_file,
        {
            'nodl_version': 2,
            'includes': [
                {'ref': 'nodl://nodl_fragment_a/all_endpoints'},
                {'ref': 'nodl://nodl_fragment_a/sub_imu'},
            ],
        },
    )
    stderr = _load_nodl_subprocess_error(test_ws_env, main_file)
    assert 'sub_a' in stderr


def test_merge_conflict_service_servers(test_ws_env, tmp_path):
    """Two includes declare same service server with different type → error."""
    main_file = tmp_path / 'main.nodl.yaml'
    _write_yaml(
        main_file,
        {
            'nodl_version': 2,
            'includes': [
                {'ref': 'nodl://nodl_fragment_a/all_endpoints'},
                {'ref': 'nodl://nodl_fragment_a/srv_set_bool_trigger'},
            ],
        },
    )
    stderr = _load_nodl_subprocess_error(test_ws_env, main_file)
    assert 'set_bool' in stderr


def test_merge_conflict_service_clients(test_ws_env, tmp_path):
    """Two includes declare same service client with different type → error."""
    main_file = tmp_path / 'main.nodl.yaml'
    _write_yaml(
        main_file,
        {
            'nodl_version': 2,
            'includes': [
                {'ref': 'nodl://nodl_fragment_a/all_endpoints'},
                {'ref': 'nodl://nodl_fragment_a/cli_trigger_setbool'},
            ],
        },
    )
    stderr = _load_nodl_subprocess_error(test_ws_env, main_file)
    assert 'trigger' in stderr


def test_merge_conflict_action_servers(test_ws_env, tmp_path):
    """Two includes declare same action server with different type → error."""
    main_file = tmp_path / 'main.nodl.yaml'
    _write_yaml(
        main_file,
        {
            'nodl_version': 2,
            'includes': [
                {'ref': 'nodl://nodl_fragment_a/all_endpoints'},
                {'ref': 'nodl://nodl_fragment_a/act_navigate_spin'},
            ],
        },
    )
    stderr = _load_nodl_subprocess_error(test_ws_env, main_file)
    assert 'navigate' in stderr


def test_merge_conflict_action_clients(test_ws_env, tmp_path):
    """Two includes declare same action client with different type → error."""
    main_file = tmp_path / 'main.nodl.yaml'
    _write_yaml(
        main_file,
        {
            'nodl_version': 2,
            'includes': [
                {'ref': 'nodl://nodl_fragment_a/all_endpoints'},
                {'ref': 'nodl://nodl_fragment_a/act_cli_spin_nav'},
            ],
        },
    )
    stderr = _load_nodl_subprocess_error(test_ws_env, main_file)
    assert 'spin' in stderr


def test_merge_conflict_parameters(test_ws_env, tmp_path):
    """Two includes declare same parameter with different default → error."""
    main_file = tmp_path / 'main.nodl.yaml'
    _write_yaml(
        main_file,
        {
            'nodl_version': 2,
            'includes': [
                {'ref': 'nodl://nodl_fragment_a/speed_v1'},
                {'ref': 'nodl://nodl_fragment_a/speed_v99'},
            ],
        },
    )
    stderr = _load_nodl_subprocess_error(test_ws_env, main_file)
    assert 'speed' in stderr


def test_merge_conflict_parameters_different_type(test_ws_env, tmp_path):
    """Two includes declare same parameter with different type → error."""
    main_file = tmp_path / 'main.nodl.yaml'
    _write_yaml(
        main_file,
        {
            'nodl_version': 2,
            'includes': [
                {'ref': 'nodl://nodl_fragment_a/speed_v1'},
                {'ref': 'nodl://nodl_fragment_a/speed_int'},
            ],
        },
    )
    stderr = _load_nodl_subprocess_error(test_ws_env, main_file)
    assert 'speed' in stderr


# ---------------------------------------------------------------------------
# Conflict on QoS difference (same name, same type, different QoS)
# ---------------------------------------------------------------------------


def test_merge_conflict_publisher_qos_difference(test_ws_env, tmp_path):
    """Same-name, same-type publisher with different QoS → error."""
    main_file = tmp_path / 'main.nodl.yaml'
    _write_yaml(
        main_file,
        {
            'nodl_version': 2,
            'includes': [
                {'ref': 'nodl://nodl_fragment_a/topic_a_rel_d1'},
                {'ref': 'nodl://nodl_fragment_a/topic_a_be_d1'},
            ],
        },
    )
    stderr = _load_nodl_subprocess_error(test_ws_env, main_file)
    assert 'topic_a' in stderr


def test_merge_conflict_publisher_depth_difference(test_ws_env, tmp_path):
    """Same-name, same-type publisher with different queue depth → error."""
    main_file = tmp_path / 'main.nodl.yaml'
    _write_yaml(
        main_file,
        {
            'nodl_version': 2,
            'includes': [
                {'ref': 'nodl://nodl_fragment_a/topic_a_rel_d1'},
                {'ref': 'nodl://nodl_fragment_a/topic_a_rel_d10'},
            ],
        },
    )
    stderr = _load_nodl_subprocess_error(test_ws_env, main_file)
    assert 'topic_a' in stderr


# ---------------------------------------------------------------------------
# Local-wins for parameters
# ---------------------------------------------------------------------------


def test_local_parameter_wins_over_include(test_ws_env, tmp_path):
    """Same-name parameter declared locally and in include → local wins."""
    main_file = tmp_path / 'main.nodl.yaml'
    _write_yaml(
        main_file,
        {
            'nodl_version': 2,
            'includes': [{'ref': 'nodl://nodl_fragment_a/speed_v99'}],
            'parameters': {'speed': {'type': 'double', 'default_value': 1.0}},
        },
    )
    doc = _load_nodl_subprocess(test_ws_env, main_file)
    assert doc['parameters']['speed']['default_value'] == 1.0


def test_load_nodl_includes_stripped_from_result(test_ws_env, tmp_path):
    """Merged NodlDocument has no includes field."""
    main_file = tmp_path / 'main.nodl.yaml'
    _write_yaml(
        main_file,
        {
            'nodl_version': 2,
            'includes': [{'ref': 'nodl://nodl_fragment_a/topic_a'}],
        },
    )
    doc = _load_nodl_subprocess(test_ws_env, main_file)
    assert 'includes' not in doc


def test_load_nodl_nested_includes(test_ws_env, tmp_path):
    """A includes B, B includes C → C's interface appears in A."""
    main_file = tmp_path / 'main.nodl.yaml'
    _write_yaml(
        main_file,
        {
            'nodl_version': 2,
            'includes': [{'ref': 'nodl://nodl_fragment_a/wraps_diagnostics'}],
        },
    )
    doc = _load_nodl_subprocess(test_ws_env, main_file)
    pub_names = [p['name'] for p in doc.get('publishers', [])]
    assert '/diagnostics' in pub_names


def test_load_nodl_circular_include_handled(test_ws_env, tmp_path):
    """A includes B, B includes A → terminates gracefully."""
    main_file = tmp_path / 'main.nodl.yaml'
    _write_yaml(
        main_file,
        {
            'nodl_version': 2,
            'includes': [{'ref': 'nodl://nodl_fragment_a/circular_a'}],
        },
    )
    doc = _load_nodl_subprocess(test_ws_env, main_file)
    pub_names = {p['name'] for p in doc.get('publishers', [])}
    assert '/from_circular_a' in pub_names
    assert '/from_circular_b' in pub_names
