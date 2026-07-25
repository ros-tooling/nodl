# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Session-scoped fixtures for nodl_schema integration tests.

Builds the embedded test workspace once per session and provides an
environment dict where the test packages are installed into the ament
index, so ``nodl://`` URIs resolve through the real ament resource index.

Adapted from the launch_interface test harness.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

TEST_WS = Path(__file__).parent / 'test_ws'


@pytest.fixture(scope='session')
def test_ws_env() -> dict[str, str]:
    """Build the test workspace and return an environment with it sourced."""
    install_dir = TEST_WS / 'install'

    # Build only if install doesn't exist or is older than the source.
    src_mtime = max(f.stat().st_mtime for f in (TEST_WS / 'src').rglob('*') if f.is_file())
    needs_build = not install_dir.exists() or install_dir.stat().st_mtime < src_mtime

    if needs_build:
        env = os.environ.copy()
        # Ensure runtime library dirs are also visible to the build-time
        # linker so that -l flags resolve correctly.
        ld_lib = env.get('LD_LIBRARY_PATH', '')
        if ld_lib:
            existing = env.get('LIBRARY_PATH', '')
            env['LIBRARY_PATH'] = ld_lib + (':' + existing if existing else '')

        subprocess.check_call(
            ['colcon', 'build', '--base-paths', 'src'],
            cwd=str(TEST_WS),
            env=env,
        )

    # Source local_setup.bash (not setup.bash) to avoid chaining to
    # whatever underlay was active at build time.
    #
    # Strip outer colcon overlay entries from AMENT_PREFIX_PATH and
    # CMAKE_PREFIX_PATH before sourcing. Heuristic: remove entries
    # containing '/install/', which matches colcon install prefixes but
    # not stock ROS (/opt/ros/<distro>) or pixi-managed ROS
    # (.pixi/envs/default).
    setup_bash = install_dir / 'local_setup.bash'
    assert setup_bash.exists(), f'local_setup.bash not found at {setup_bash}'

    child_env = os.environ.copy()
    for var in ('AMENT_PREFIX_PATH', 'CMAKE_PREFIX_PATH'):
        if var not in child_env:
            continue
        kept = [entry for entry in child_env[var].split(os.pathsep) if entry and '/install/' not in entry]
        child_env[var] = os.pathsep.join(kept)

    result = subprocess.run(
        ['bash', '-c', f'source {setup_bash} && env -0'],
        capture_output=True,
        text=True,
        check=True,
        env=child_env,
    )

    env = {}
    for entry in result.stdout.split('\0'):
        if '=' in entry:
            key, _, value = entry.partition('=')
            env[key] = value

    return env
