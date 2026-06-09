# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Layer-3 rendering tests: golden ``Node.msg`` in, golden text out.

These exercise the serialization layer (:mod:`nodl_observe.serialization`) with
**no executor and no graph** -- the only ROS dependency is the message package
itself, used to load each layer-2 YAML golden back into a
``rosgraph_msgs/Node`` via :func:`rosidl_runtime_py.set_message_fields`.  That
is what "no ROS env" means here: no spinning, no discovery -- just message
introspection.  Renderer bugs never require standing up a node to find.

A single YAML golden per ``(distro, RMW)`` is the committed canonical form --
it is the human-readable render, the stdout default, and the #53 input fixture.
We do *not* commit a second JSON golden of the same message: JSON is the same
information in a less diff-friendly shape, so its renderer is proven by
*equivalence* (render both from the loaded message; their parsed structures
must be equal) rather than by a duplicate file.  For every YAML golden we
assert:

* ``to_yaml`` of the reloaded message is byte-identical to the golden
  (round-trip identity -- the YAML *is* the canonical form), and
* ``to_json`` of the same message parses to the same structure as the YAML
  (the JSON renderer is faithful), needing no committed JSON golden.
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

# Same deduplicated golden resolution as the layer-2 integration tests, which
# produce these inputs: most-specific first over expected/<distro>/<rmw>/, then
# expected/<rmw>/, then expected/_base/.  (Kept in sync with that module; the
# two test layers are independent so a shared import would couple collection.)
_ROS_DISTRO = os.environ.get('ROS_DISTRO', 'unknown')
_RMW = os.environ.get('RMW_IMPLEMENTATION', 'rmw_fastrtps_cpp')
_EXPECTED = os.path.join(os.path.dirname(__file__), 'expected')

# The layer-2 goldens that feed these rendering tests.
_GOLDENS = ['s1_node', 's2_node', 's3_node_a', 's3_node_b']


def _resolve_golden(basename):
    """Return the golden path for *basename*, most-specific first, or ``None``."""
    for directory in (os.path.join(_EXPECTED, _ROS_DISTRO, _RMW),
                      os.path.join(_EXPECTED, _RMW),
                      os.path.join(_EXPECTED, '_base')):
        path = os.path.join(directory, f'{basename}.yaml')
        if os.path.exists(path):
            return path
    return None


if _resolve_golden('s1_node') is None:
    pytest.skip(
        f'no goldens for ROS distro {_ROS_DISTRO!r} / RMW {_RMW!r}; run the '
        'integration tests with REGEN_GOLDENS=1 to bootstrap them',
        allow_module_level=True)


def _load_message(basename):
    """Load the resolved YAML golden back into a ``Node`` message."""
    path = _resolve_golden(basename)
    assert path is not None, (
        f'Missing layer-2 golden for {basename!r}; run the integration tests '
        'with REGEN_GOLDENS=1 first.')
    with open(path) as fh:
        data = yaml.safe_load(fh.read())
    msg = NodeMsg()
    set_message_fields(msg, data)
    return msg


@pytest.mark.parametrize('basename', _GOLDENS)
def test_yaml_round_trip_identity(basename):
    """Reloading a YAML golden and re-rendering it yields the same bytes."""
    with open(_resolve_golden(basename)) as fh:
        golden_yaml = fh.read()
    msg = _load_message(basename)
    assert to_yaml(msg) == golden_yaml, (
        f'{basename}: YAML render is not a fixed point of its own golden.')


@pytest.mark.parametrize('basename', _GOLDENS)
def test_json_render_equivalent_to_yaml(basename):
    """JSON render carries the same structure as the YAML golden (no JSON golden).

    Proves the ``-o file.json`` path is faithful without committing a second
    representation of the same message: both renders, parsed, must be equal.
    """
    msg = _load_message(basename)
    from_json = json.loads(to_json(msg))
    from_yaml = yaml.safe_load(to_yaml(msg))
    assert from_json == from_yaml, (
        f'{basename}: JSON render diverges from the YAML structure.')
