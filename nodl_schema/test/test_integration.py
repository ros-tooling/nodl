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
# Phase 3: load_nodl() resolves package URIs via the ament index
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
