# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Layer-2 observation integration tests: scenario graphs -> golden YAML.

Each scenario spins a *dummy ROS environment* in-process -- the scenario nodes
on a background executor, plus a separate observer node -- runs
:func:`observe_node`, renders the result with
:func:`nodl_observe.serialization.to_yaml`, and diffs it against a committed
golden file in ``test/expected/``.

A failing diff reads as "what changed in the observed interface", which is far
better signal than an opaque ``assert``.  The goldens double as the input
fixtures for Describe (#53): they are real ``rosgraph_msgs/Node`` samples.

Isolation
---------
Stray nodes on the host must not leak into the observed graph.  The scenarios
run under ``ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST`` and a per-run, *derived*
(not random) ``ROS_DOMAIN_ID``, with ``RMW_IMPLEMENTATION`` pinned to
``rmw_fastrtps_cpp`` because QoS introspection results can differ per RMW.
These are set in :func:`_isolate_ros_env` *before* the first ``rclpy.init`` so
the colcon test runner picks them up regardless of how it is invoked.  Nothing
in the golden content depends on the domain id or hostname; a dedicated test
asserts that.

Golden regeneration
-------------------
Set ``REGEN_GOLDENS=1`` to (re)write the goldens instead of diffing.  The
maintainer is expected to inspect the regenerated files before committing.
"""

import os
import threading

import pytest

# Guard: skip the whole module if the ROS stack is absent (e.g. macOS host) or
# too old.  Importing nodl_observe (rather than rosgraph_msgs) is what catches
# distros whose rosgraph_msgs predates 2.0.4 and therefore lacks Node.msg.
rclpy = pytest.importorskip('rclpy')
pytest.importorskip('nodl_observe')


def _isolate_ros_env():
    """Pin the RMW + an isolated, derived domain before rclpy is initialised."""
    # Derived (deterministic per process), NOT random -- but golden content must
    # not depend on it, which a separate test enforces.
    domain_id = str(os.getpid() % 100 + 100)  # 100..199, away from common ids
    os.environ.setdefault('ROS_DOMAIN_ID', domain_id)
    os.environ.setdefault('ROS_AUTOMATIC_DISCOVERY_RANGE', 'LOCALHOST')
    os.environ.setdefault('RMW_IMPLEMENTATION', 'rmw_fastrtps_cpp')


_isolate_ros_env()

import rclpy.qos  # noqa: E402  (after importorskip + env isolation)

from example_interfaces.action import Fibonacci  # noqa: E402
from example_interfaces.srv import AddTwoInts  # noqa: E402

from rcl_interfaces.msg import ParameterDescriptor  # noqa: E402

from rclpy.action import ActionClient, ActionServer  # noqa: E402
from rclpy.duration import Duration  # noqa: E402
from rclpy.executors import SingleThreadedExecutor  # noqa: E402
from rclpy.node import Node  # noqa: E402
from rclpy.qos import (  # noqa: E402
    DurabilityPolicy,
    HistoryPolicy,
    QoSProfile,
    ReliabilityPolicy,
)

from std_msgs.msg import String  # noqa: E402

from nodl_observe import observe_node  # noqa: E402
from nodl_observe.serialization import to_yaml  # noqa: E402

# Goldens are per-distro: implicit endpoint sets, QoS observability, and type
# hashes can all shift between ROS releases, so each distro in CI carries its
# own golden set.  A distro without goldens skips (with a bootstrap hint)
# rather than diffing against another release's files.
_ROS_DISTRO = os.environ.get('ROS_DISTRO', 'unknown')
_EXPECTED_DIR = os.path.join(os.path.dirname(__file__), 'expected', _ROS_DISTRO)
_REGEN = os.environ.get('REGEN_GOLDENS') == '1'
_OBSERVE_TIMEOUT = 10.0

if not _REGEN and not os.path.isdir(_EXPECTED_DIR):
    pytest.skip(
        f'no goldens for ROS distro {_ROS_DISTRO!r} (expected at '
        f'{_EXPECTED_DIR}); run with REGEN_GOLDENS=1 to bootstrap them',
        allow_module_level=True)


@pytest.fixture(scope='session', autouse=True)
def _ros_session():
    """Init/shutdown rclpy once for the whole module's scenario graphs."""
    rclpy.init()
    yield
    rclpy.shutdown()


# --------------------------------------------------------------------------- #
# Scenario graph builders
# --------------------------------------------------------------------------- #


def _build_s1(_ctx):
    """S1 minimal: 1 node, 1 pub, 1 sub, all default QoS."""
    node = Node('s1_node', namespace='/s1')
    node.create_publisher(String, 'chatter', 10)
    node.create_subscription(String, 'commands', lambda _m: None, 10)
    return [node]


def _build_s2(_ctx):
    """S2 full-surface: every endpoint kind, QoS deliberately varied."""
    node = Node('s2_node', namespace='/s2')

    # 3 parameters, one read-only.
    node.declare_parameter('speed', 1.5)
    node.declare_parameter('max_count', 10)
    node.declare_parameter(
        'mode', 'auto',
        ParameterDescriptor(description='operating mode', read_only=True))

    # Topics with deliberately varied QoS across the enum space.
    node.create_publisher(
        String, 'be_pub',
        QoSProfile(depth=10, reliability=ReliabilityPolicy.BEST_EFFORT,
                   history=HistoryPolicy.KEEP_LAST))
    node.create_publisher(
        String, 'tl_pub',
        QoSProfile(depth=1, reliability=ReliabilityPolicy.RELIABLE,
                   durability=DurabilityPolicy.TRANSIENT_LOCAL,
                   history=HistoryPolicy.KEEP_ALL))
    node.create_subscription(
        String, 'dl_sub', lambda _m: None,
        QoSProfile(depth=5, deadline=Duration(seconds=2)))

    # Service server + client, both with explicit non-default QoS.  The golden
    # must still show *_UNKNOWN -- service QoS is not observable (the documented
    # can't-observe limitation, locked in as a test).
    non_default_srv_qos = QoSProfile(
        depth=3, reliability=ReliabilityPolicy.BEST_EFFORT,
        durability=DurabilityPolicy.TRANSIENT_LOCAL,
        history=HistoryPolicy.KEEP_ALL)
    node.create_service(AddTwoInts, 'add', lambda _req, resp: resp,
                        qos_profile=non_default_srv_qos)
    node.create_client(AddTwoInts, 'multiply', qos_profile=non_default_srv_qos)

    # Action server + client -> their _action/* constituents must be folded.
    ActionServer(node, Fibonacci, 'fib', lambda goal: goal)
    ActionClient(node, Fibonacci, 'compute')
    return [node]


def _build_s3(_ctx):
    """S3 multi-node isolation: A (target) and B share a topic with different QoS."""
    node_a = Node('node_a', namespace='/s3')
    node_b = Node('node_b', namespace='/s3')

    # A and B both touch /s3/shared, but with QoS that differs from each other,
    # so attribution (and QoS cross-attribution) is exercised.
    node_a.create_publisher(
        String, '/s3/shared',
        QoSProfile(depth=10, reliability=ReliabilityPolicy.RELIABLE,
                   history=HistoryPolicy.KEEP_LAST))
    node_b.create_subscription(
        String, '/s3/shared', lambda _m: None,
        QoSProfile(depth=1, reliability=ReliabilityPolicy.BEST_EFFORT,
                   history=HistoryPolicy.KEEP_LAST))

    # A also has a private subscription; B has its own service + action.
    node_a.create_subscription(String, '/s3/a_only', lambda _m: None, 10)
    node_b.create_service(AddTwoInts, 'b_add', lambda _req, resp: resp)
    ActionServer(node_b, Fibonacci, 'b_fib', lambda goal: goal)
    return [node_a, node_b]


# Each scenario: builder + the (target_fqn, golden_basename) pairs to observe.
_SCENARIOS = {
    's1': (_build_s1, [('/s1/s1_node', 's1_node')]),
    's2': (_build_s2, [('/s2/s2_node', 's2_node')]),
    's3': (_build_s3, [
        ('/s3/node_a', 's3_node_a'),
        ('/s3/node_b', 's3_node_b'),
    ]),
}


# --------------------------------------------------------------------------- #
# Harness
# --------------------------------------------------------------------------- #


class _ScenarioGraph:
    """Spins scenario nodes on a background executor and observes from another node."""

    def __init__(self, builder):
        self._builder = builder
        self.nodes = []
        self._observer = None
        self._executor = None
        self._thread = None

    def __enter__(self):
        self.nodes = self._builder(None)
        self._observer = Node('_nodl_observe_test_observer')
        self._executor = SingleThreadedExecutor()
        for node in self.nodes:
            self._executor.add_node(node)
        self._thread = threading.Thread(target=self._executor.spin, daemon=True)
        self._thread.start()
        return self

    def observe(self, target_fqn):
        return observe_node(self._observer, target_fqn, timeout_sec=_OBSERVE_TIMEOUT)

    def __exit__(self, *exc):
        self._executor.shutdown()
        self._thread.join(timeout=3.0)
        self._observer.destroy_node()
        for node in self.nodes:
            node.destroy_node()
        return False


def _golden_path(basename):
    return os.path.join(_EXPECTED_DIR, f'{basename}.yaml')


def _observe_scenario(scenario):
    """Run one scenario, returning ``{basename: yaml_text}`` for every target."""
    builder, targets = _SCENARIOS[scenario]
    rendered = {}
    with _ScenarioGraph(builder) as graph:
        for target_fqn, basename in targets:
            msg = graph.observe(target_fqn)
            rendered[basename] = to_yaml(msg)
    return rendered


# Module-scoped cache: observe each scenario's graph exactly once, even though
# several tests assert against the same render.  Spinning a graph per assertion
# would be slow and risk discovery flakiness.
_RENDER_CACHE = {}


def _render(scenario):
    if scenario not in _RENDER_CACHE:
        _RENDER_CACHE[scenario] = _observe_scenario(scenario)
    return _RENDER_CACHE[scenario]


# --------------------------------------------------------------------------- #
# Golden comparison tests
# --------------------------------------------------------------------------- #


_ALL_TARGETS = [
    (scenario, basename)
    for scenario, (_b, targets) in _SCENARIOS.items()
    for _fqn, basename in targets
]


@pytest.mark.parametrize('scenario,basename', _ALL_TARGETS)
def test_observation_matches_golden(scenario, basename):
    """Observed YAML matches the committed golden (or regenerates it)."""
    actual = _render(scenario)[basename]
    path = _golden_path(basename)

    if _REGEN:
        os.makedirs(_EXPECTED_DIR, exist_ok=True)
        with open(path, 'w') as fh:
            fh.write(actual)
        pytest.skip(f'REGEN_GOLDENS: wrote {path}')

    assert os.path.exists(path), (
        f'Missing golden {path!r}. Run with REGEN_GOLDENS=1 to generate it.')
    with open(path) as fh:
        expected = fh.read()
    assert actual == expected, (
        f'Observation of {basename} drifted from its golden.\n'
        f'Re-run with REGEN_GOLDENS=1 if this change is intended.')


# --------------------------------------------------------------------------- #
# Targeted assertions per scenario (each traces to an observer failure mode)
# --------------------------------------------------------------------------- #


def _find(endpoints, name):
    """Find an endpoint by name, naming the candidates when it is missing."""
    for endpoint in endpoints:
        if endpoint.name == name:
            return endpoint
    raise AssertionError(
        f'no endpoint named {name!r}; present: '
        f'{sorted(e.name for e in endpoints)}')


def _node_from_golden(basename):
    """Load a rendered golden back into a ``Node`` message for field assertions."""
    import yaml
    from rosgraph_msgs.msg import Node as NodeMsg
    from rosidl_runtime_py import set_message_fields
    msg = NodeMsg()
    set_message_fields(msg, yaml.safe_load(_render_or_golden(basename)))
    return msg


def _render_or_golden(basename):
    # Prefer the live render so these assertions exercise the real observation;
    # they share the cache with the golden test.
    for scenario, (_b, targets) in _SCENARIOS.items():
        for _fqn, name in targets:
            if name == basename:
                return _render(scenario)[basename]
    raise KeyError(basename)


class TestS1Minimal:
    """Baseline: implicit endpoints present + unfiltered, type hash correct."""

    def test_user_topics_present_with_type_hash(self):
        msg = _node_from_golden('s1_node')
        chatter = _find(msg.publishers, '/s1/chatter')
        assert chatter.type.name == 'std_msgs/msg/String'
        # Topic type hash must be a real, populated RIHS hash, not all-zero.
        assert any(b != 0 for b in bytes(chatter.type.hash.value))
        sub = _find(msg.subscriptions, '/s1/commands')
        assert sub.type.name == 'std_msgs/msg/String'

    def test_implicit_endpoints_unfiltered(self):
        msg = _node_from_golden('s1_node')
        pub_names = {p.name for p in msg.publishers}
        srv_names = {s.name for s in msg.service_servers}
        # /rosout + /parameter_events stay flat and unfiltered (Observe records).
        assert '/rosout' in pub_names
        assert '/parameter_events' in pub_names
        # The implicit parameter services are all present.
        for suffix in ('list_parameters', 'describe_parameters', 'get_parameters',
                       'set_parameters', 'set_parameters_atomically',
                       'get_parameter_types'):
            assert f'/s1/s1_node/{suffix}' in srv_names


class TestS2FullSurface:
    """Every field exercised; topic QoS across the enum space; service UNKNOWN."""

    def test_varied_topic_qos_captured(self):
        msg = _node_from_golden('s2_node')
        from rosgraph_msgs.msg import QoSProfile as QoSMsg
        be = _find(msg.publishers, '/s2/be_pub')
        assert be.qos.reliability == QoSMsg.RELIABILITY_BEST_EFFORT
        tl = _find(msg.publishers, '/s2/tl_pub')
        # TRANSIENT_LOCAL durability is observable over DDS discovery; the
        # history policy (KEEP_ALL on the wire) is *not* propagated by
        # rmw_fastrtps_cpp and comes back HISTORY_UNKNOWN -- the golden records
        # that honestly rather than fabricating the requested value.
        assert tl.qos.durability == QoSMsg.DURABILITY_TRANSIENT_LOCAL
        assert tl.qos.history == QoSMsg.HISTORY_UNKNOWN
        dl = _find(msg.subscriptions, '/s2/dl_sub')
        assert dl.qos.deadline.sec == 2

    def test_service_qos_unknown_despite_non_default_wire_qos(self):
        # The documented can't-observe limitation, locked in: services were
        # created with explicit non-default QoS, yet the observed QoS is UNKNOWN.
        msg = _node_from_golden('s2_node')
        from rosgraph_msgs.msg import QoSProfile as QoSMsg
        add = _find(msg.service_servers, '/s2/add')
        assert add.request_qos.reliability == QoSMsg.RELIABILITY_UNKNOWN
        assert add.request_qos.durability == QoSMsg.DURABILITY_UNKNOWN
        mul = _find(msg.service_clients, '/s2/multiply')
        assert mul.response_qos.reliability == QoSMsg.RELIABILITY_UNKNOWN

    def test_actions_folded_not_flat(self):
        msg = _node_from_golden('s2_node')
        server = _find(msg.action_servers, '/s2/fib')
        assert server.send_goal.name == '/s2/fib/_action/send_goal'
        assert server.feedback.name == '/s2/fib/_action/feedback'
        client = _find(msg.action_clients, '/s2/compute')
        assert client.get_result.name == '/s2/compute/_action/get_result'
        # No _action/* constituent may leak into a flat list.
        flat = ([p.name for p in msg.publishers]
                + [s.name for s in msg.subscriptions]
                + [s.name for s in msg.service_servers]
                + [s.name for s in msg.service_clients])
        assert not any('/_action/' in n for n in flat)

    def test_parameter_descriptors_and_values(self):
        msg = _node_from_golden('s2_node')
        by_name = {d.name: (d, v) for d, v in
                   zip(msg.parameters, msg.parameter_values)}
        assert 'speed' in by_name and 'max_count' in by_name and 'mode' in by_name
        mode_desc, _ = by_name['mode']
        assert mode_desc.read_only is True
        _, speed_val = by_name['speed']
        assert abs(speed_val.double_value - 1.5) < 1e-9


class TestS3Isolation:
    """By-node attribution + QoS cross-attribution on a shared topic."""

    def test_target_a_does_not_leak_node_b(self):
        msg = _node_from_golden('s3_node_a')
        flat = ([p.name for p in msg.publishers]
                + [s.name for s in msg.subscriptions]
                + [s.name for s in msg.service_servers])
        # B's private endpoints must not appear when observing A.
        assert '/s3/a_only' in flat
        assert '/s3/b_add' not in flat
        assert all('b_fib' not in n for n in flat)
        assert not msg.action_servers, "A has no actions; B's must not leak in"

    def test_shared_topic_carries_targets_own_qos(self):
        from rosgraph_msgs.msg import QoSProfile as QoSMsg
        # A publishes /s3/shared RELIABLE; B subscribes BEST_EFFORT.  Each
        # golden must carry its *own* node's QoS, never the peer's.
        msg_a = _node_from_golden('s3_node_a')
        shared_a = _find(msg_a.publishers, '/s3/shared')
        assert shared_a.qos.reliability == QoSMsg.RELIABILITY_RELIABLE
        msg_b = _node_from_golden('s3_node_b')
        shared_b = _find(msg_b.subscriptions, '/s3/shared')
        assert shared_b.qos.reliability == QoSMsg.RELIABILITY_BEST_EFFORT


# --------------------------------------------------------------------------- #
# Determinism guards
# --------------------------------------------------------------------------- #


def _string_values(obj):
    """Yield every string scalar reachable in a parsed-YAML structure.

    Numeric scalars (e.g. the integer bytes of a type-hash array) are skipped,
    so the leak check inspects only the human-meaningful fields where a domain
    id or hostname could actually appear -- not coincidental hash-byte values.
    """
    import yaml
    data = yaml.safe_load(obj)

    def walk(node):
        if isinstance(node, str):
            yield node
        elif isinstance(node, dict):
            for key, value in node.items():
                yield key
                yield from walk(value)
        elif isinstance(node, list):
            for item in node:
                yield from walk(item)

    yield from walk(data)


class TestDeterminism:
    def test_no_domain_id_or_hostname_leaked(self):
        """No string-valued golden field may encode the domain id or hostname."""
        import socket
        domain_id = os.environ.get('ROS_DOMAIN_ID', '')
        hostname = socket.gethostname()
        for scenario in _SCENARIOS:
            for basename, text in _render(scenario).items():
                strings = list(_string_values(text))
                if domain_id:
                    assert not any(domain_id in s for s in strings), (
                        f'{basename}: domain id {domain_id!r} leaked into a '
                        'string field')
                assert not any(hostname in s for s in strings), (
                    f'{basename}: hostname {hostname!r} leaked into a string '
                    'field')

    def test_endpoint_arrays_sorted(self):
        """observe_node sorts every endpoint array (name, then type)."""
        msg = _node_from_golden('s2_node')
        assert [p.name for p in msg.publishers] == sorted(
            p.name for p in msg.publishers)
        assert [s.name for s in msg.service_servers] == sorted(
            s.name for s in msg.service_servers)
        assert [p.name for p in msg.parameters] == sorted(
            p.name for p in msg.parameters)
