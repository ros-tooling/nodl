# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Layer-3 rendering tests: golden ``Node.msg`` in, golden text out.

These exercise the serialization layer (:mod:`nodl_observe.serialization`) with
**no executor and no graph** -- the only ROS dependency is the message package
itself, used to load each layer-2 YAML golden back into a
``rosgraph_msgs/Node`` via :func:`rosidl_runtime_py.set_message_fields`.  That
is what "no ROS env" means here: no spinning, no discovery -- just message
introspection.  Renderer bugs never require standing up a node to find.

For every layer-2 golden ``<name>.yaml`` we assert:

* ``to_yaml`` of the reloaded message is byte-identical to the golden
  (round-trip identity -- the YAML *is* the canonical form), and
* ``to_json`` matches a committed ``<name>.json`` golden (regenerated with the
  same ``REGEN_GOLDENS=1`` switch as layer 2, and inspected before commit).
"""

import json
import os

import pytest

# Guard: the message package must be importable, but no executor is needed.
# Importing nodl_observe (vs. rosgraph_msgs) also catches distros whose
# rosgraph_msgs predates 2.0.4 and lacks Node.msg.
pytest.importorskip('nodl_observe')
pytest.importorskip('rosidl_runtime_py')

import yaml  # noqa: E402

from rosgraph_msgs.msg import Node as NodeMsg  # noqa: E402

from rosidl_runtime_py import set_message_fields  # noqa: E402

from nodl_observe.serialization import to_json, to_yaml  # noqa: E402

# Same per-distro golden layout as the layer-2 integration tests, which
# produce these inputs.
_ROS_DISTRO = os.environ.get('ROS_DISTRO', 'unknown')
_EXPECTED_DIR = os.path.join(os.path.dirname(__file__), 'expected', _ROS_DISTRO)
_REGEN = os.environ.get('REGEN_GOLDENS') == '1'

if not _REGEN and not os.path.isdir(_EXPECTED_DIR):
    pytest.skip(
        f'no goldens for ROS distro {_ROS_DISTRO!r}; run the integration '
        'tests with REGEN_GOLDENS=1 to bootstrap them',
        allow_module_level=True)

# The layer-2 goldens that feed these rendering tests.
_GOLDENS = ['s1_node', 's2_node', 's3_node_a', 's3_node_b']


def _load_message(basename):
    """Load ``expected/<basename>.yaml`` back into a ``Node`` message."""
    path = os.path.join(_EXPECTED_DIR, f'{basename}.yaml')
    assert os.path.exists(path), (
        f'Missing layer-2 golden {path!r}; run the integration tests with '
        'REGEN_GOLDENS=1 first.')
    with open(path) as fh:
        data = yaml.safe_load(fh.read())
    msg = NodeMsg()
    set_message_fields(msg, data)
    return msg


@pytest.mark.parametrize('basename', _GOLDENS)
def test_yaml_round_trip_identity(basename):
    """Reloading a YAML golden and re-rendering it yields the same bytes."""
    yaml_path = os.path.join(_EXPECTED_DIR, f'{basename}.yaml')
    with open(yaml_path) as fh:
        golden_yaml = fh.read()
    msg = _load_message(basename)
    assert to_yaml(msg) == golden_yaml, (
        f'{basename}: YAML render is not a fixed point of its own golden.')


@pytest.mark.parametrize('basename', _GOLDENS)
def test_json_matches_golden(basename):
    """JSON render matches the committed ``.json`` golden (or regenerates it)."""
    msg = _load_message(basename)
    actual = to_json(msg)
    json_path = os.path.join(_EXPECTED_DIR, f'{basename}.json')

    if _REGEN:
        os.makedirs(_EXPECTED_DIR, exist_ok=True)
        with open(json_path, 'w') as fh:
            fh.write(actual)
        pytest.skip(f'REGEN_GOLDENS: wrote {json_path}')

    assert os.path.exists(json_path), (
        f'Missing JSON golden {json_path!r}. Run with REGEN_GOLDENS=1.')
    with open(json_path) as fh:
        expected = fh.read()
    assert actual == expected, (
        f'{basename}: JSON render drifted from its golden.')
    # And it must be valid, parseable JSON describing the same node.
    parsed = json.loads(actual)
    assert parsed['name'] == msg.name
