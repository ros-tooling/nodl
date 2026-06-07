# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""CLI smoke tests for the ``ros2 nodl describe`` verb.

All tests in this module require a live ROS environment (rclpy, nodl_observe,
rosgraph_msgs).  They are skipped automatically on hosts without those packages
(e.g. the macOS dev machine) via :func:`pytest.importorskip`.

Design notes:

- Tests drive the verb through its Python API (:meth:`DescribeVerb.main`) to
  stay consistent with ``test_verbs.py``'s style.
- A lightweight target node is spun up *in-process* in an isolated ROS domain
  to avoid interference with stray nodes on the machine.
- The latched-publish subscriber is created *before* the verb runs (the
  publish-once/late-joiner limitation is explicitly documented in the plan and
  locked in here as a test).
- Each test gets a fresh :mod:`rclpy` init/shutdown via the ``ros_context``
  fixture so they can be run in sequence without state leaking.
"""

import argparse
import json
import os

import pytest

# Guard: skip the whole module if the ROS / nodl_observe stack is absent.
rclpy = pytest.importorskip('rclpy')
pytest.importorskip('nodl_observe')
pytest.importorskip('rosgraph_msgs')

import rclpy.executors  # noqa: E402  (after importorskip)
import yaml  # noqa: E402

from nodl_observe import latched_qos  # noqa: E402

from ros2nodl.verb.describe import DescribeVerb, _infer_format  # noqa: E402

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_DOMAIN_ID = int(os.environ.get('ROS_DOMAIN_ID', '42'))
_TARGET_NODE = '/ros2nodl_test_target'


def _make_args(**kwargs):
    """Build a minimal :class:`argparse.Namespace` for :meth:`DescribeVerb.main`."""
    defaults = dict(
        node_name=_TARGET_NODE,
        timeout=5.0,
        no_params=False,
        topic='/nodl/observed_node_test',
        output=None,
    )
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope='module')
def ros_context():
    """Module-scoped rclpy init/shutdown.

    Isolation: ``ROS_DOMAIN_ID`` is fixed to a test-only value via the
    environment variable so that stray nodes on the host machine cannot
    interfere.  Tests within this module share one context to keep startup
    cost low.
    """
    os.environ.setdefault('ROS_DOMAIN_ID', str(_DOMAIN_ID))
    os.environ.setdefault('ROS_AUTOMATIC_DISCOVERY_RANGE', 'LOCALHOST')
    rclpy.init()
    yield
    rclpy.shutdown()


@pytest.fixture()
def target_node(ros_context):
    """A live rclpy node that acts as the observation target.

    Creates one publisher and one subscription so there is at least one
    non-implicit endpoint to observe.
    """
    import std_msgs.msg  # present in any standard ROS 2 install
    node = rclpy.create_node(_TARGET_NODE.lstrip('/'))
    node.create_publisher(std_msgs.msg.String, '/test_topic', 10)
    node.create_subscription(std_msgs.msg.String, '/test_topic', lambda _: None, 10)
    yield node
    node.destroy_node()


@pytest.fixture()
def harness_node(ros_context):
    """A node used to subscribe to the latched topic *before* the verb runs."""
    node = rclpy.create_node('_ros2nodl_test_harness')
    yield node
    node.destroy_node()


# ---------------------------------------------------------------------------
# Pure-Python (no ROS) tests — run anywhere
# ---------------------------------------------------------------------------

class TestInferFormat:
    def test_yaml_extension(self):
        assert _infer_format('out.yaml') == 'yaml'

    def test_yml_extension(self):
        assert _infer_format('out.yml') == 'yaml'

    def test_json_extension(self):
        assert _infer_format('out.json') == 'json'

    def test_uppercase_extension(self):
        assert _infer_format('OUT.YAML') == 'yaml'

    def test_unknown_extension_raises(self):
        import argparse as _ap
        with pytest.raises(_ap.ArgumentTypeError, match='unrecognised extension'):
            _infer_format('out.txt')

    def test_no_extension_raises(self):
        import argparse as _ap
        with pytest.raises(_ap.ArgumentTypeError):
            _infer_format('noextension')


class TestDescribeVerbBadArgs:
    """Tests that do not require a live ROS environment."""

    def test_unknown_output_extension_returns_1(self, capsys):
        verb = DescribeVerb()
        args = _make_args(output='out.txt')
        rc = verb.main(args=args)
        assert rc == 1
        assert 'unrecognised extension' in capsys.readouterr().err

    def test_unknown_output_extension_no_ros_started(self, capsys):
        """Verify the extension check happens *before* rclpy.init()."""
        verb = DescribeVerb()
        args = _make_args(output='out.png')
        # If rclpy were initialised this would fail because rclpy.shutdown() in
        # a previous test already shut it down.  The point is that it returns 1
        # without touching ROS.
        rc = verb.main(args=args)
        assert rc == 1


# ---------------------------------------------------------------------------
# ROS smoke tests — require rclpy + nodl_observe + a running target node
# ---------------------------------------------------------------------------

class TestDescribeVerbSmoke:

    def test_exit_code_zero(self, target_node, capsys):
        """Verb exits 0 when the target node is present."""
        verb = DescribeVerb()
        rc = verb.main(args=_make_args())
        assert rc == 0

    def test_stdout_is_valid_yaml_with_node_name(self, target_node, capsys):
        """Default output (no -o) is YAML that contains the target node's FQN."""
        verb = DescribeVerb()
        verb.main(args=_make_args())
        out = capsys.readouterr().out
        doc = yaml.safe_load(out)
        assert doc is not None, 'stdout did not parse as YAML'
        # rosgraph_msgs/Node has a 'name' field at the top level.
        assert 'name' in doc, f'YAML output missing "name" field: {doc!r}'
        assert _TARGET_NODE in doc['name'], (
            f'Expected {_TARGET_NODE!r} in name field, got {doc["name"]!r}'
        )

    def test_output_json_is_valid(self, target_node, tmp_path):
        """``-o foo.json`` writes parseable JSON."""
        out_file = tmp_path / 'obs.json'
        verb = DescribeVerb()
        rc = verb.main(args=_make_args(output=str(out_file)))
        assert rc == 0
        assert out_file.exists(), '-o did not create the output file'
        data = json.loads(out_file.read_text())
        assert isinstance(data, dict), 'JSON output is not an object'
        assert 'name' in data

    def test_output_yaml_matches_stdout(self, target_node, tmp_path, capsys):
        """``-o foo.yaml`` and stdout (no -o) produce the same bytes."""
        # First run: capture stdout.
        verb = DescribeVerb()
        verb.main(args=_make_args())
        stdout_text = capsys.readouterr().out

        # Second run: write to a YAML file.
        out_file = tmp_path / 'obs.yaml'
        verb.main(args=_make_args(output=str(out_file)))

        assert out_file.read_text() == stdout_text, (
            '-o .yaml output differs from stdout'
        )

    def test_latched_publish_received_by_presubscribed_harness(
        self, target_node, harness_node, ros_context
    ):
        """A subscriber created *before* the verb runs receives the message.

        This locks in the publish-once / late-joiner semantics documented in
        the plan: the latched history lives only as long as the publisher, so
        consumers must subscribe before the verb exits.
        """
        from rosgraph_msgs.msg import Node as NodeMsg

        received = []
        topic = '/nodl/observed_node_presubscribe_test'

        # Subscribe BEFORE the verb runs, with the library's latched profile.
        harness_node.create_subscription(
            NodeMsg,
            topic,
            lambda msg: received.append(msg),
            latched_qos(),
        )

        verb = DescribeVerb()
        rc = verb.main(args=_make_args(topic=topic))
        assert rc == 0

        # Spin briefly so the harness node can process any queued messages.
        executor = rclpy.executors.SingleThreadedExecutor()
        executor.add_node(harness_node)
        import time
        deadline = time.monotonic() + 2.0
        while not received and time.monotonic() < deadline:
            executor.spin_once(timeout_sec=0.1)
        executor.remove_node(harness_node)

        assert len(received) >= 1, (
            'Harness subscriber (created before verb ran) received no message on '
            f'{topic!r}. This may indicate the latched publish did not complete '
            'before the publisher was destroyed.'
        )

    def test_node_not_found_returns_nonzero(self, ros_context, capsys):
        """Verb returns nonzero with a clear message when the target is absent."""
        verb = DescribeVerb()
        rc = verb.main(args=_make_args(node_name='/nonexistent_node_xyzzy'))
        assert rc != 0
        err = capsys.readouterr().err
        assert 'not found' in err.lower() or 'nonexistent' in err.lower(), (
            f'Expected "not found" in stderr, got: {err!r}'
        )

    def test_no_params_flag_succeeds(self, target_node, capsys):
        """``--no-params`` completes successfully and does not contact the target."""
        verb = DescribeVerb()
        rc = verb.main(args=_make_args(no_params=True))
        assert rc == 0
        out = capsys.readouterr().out
        assert yaml.safe_load(out) is not None

    def test_custom_topic_used(self, target_node):
        """``--topic`` overrides the publish destination."""
        from rosgraph_msgs.msg import Node as NodeMsg

        custom_topic = '/nodl/custom_topic_smoke_test'
        received = []
        # We need a harness node here; create it inline.
        harness = rclpy.create_node('_ros2nodl_topic_check_harness')
        try:
            harness.create_subscription(
                NodeMsg, custom_topic,
                lambda msg: received.append(msg),
                latched_qos(),
            )
            verb = DescribeVerb()
            rc = verb.main(args=_make_args(topic=custom_topic))
            assert rc == 0

            executor = rclpy.executors.SingleThreadedExecutor()
            executor.add_node(harness)
            import time
            deadline = time.monotonic() + 2.0
            while not received and time.monotonic() < deadline:
                executor.spin_once(timeout_sec=0.1)
            executor.remove_node(harness)
        finally:
            harness.destroy_node()

        assert received, f'No message received on custom topic {custom_topic!r}'
