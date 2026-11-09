# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0

import signal
from pathlib import Path

import pytest
import rclpy
from rclpy.lifecycle import LifecyclePublisher, SimpleManagedEntity, TransitionCallbackReturn
from std_msgs.msg import String

from nodl_runtime_py.lifecycle import LifecycleNode

SUCCESS = TransitionCallbackReturn.SUCCESS
FAILURE = TransitionCallbackReturn.FAILURE
ERROR = TransitionCallbackReturn.ERROR

EXAMPLES_DIR = Path(__file__).parent.parent / 'doc' / 'examples'
HOOKS = ('configure', 'activate', 'deactivate', 'cleanup', 'shutdown', 'error')


class RecordingNode(LifecycleNode):
    """Record each hook with whether its lifecycle publisher was active, and return a configurable result."""

    def __init__(self, results=None):
        super().__init__('recording_node')
        self.results = results or {}
        self.calls = []
        self.publisher = self.create_lifecycle_publisher(String, 'topic', 10)

    def _record(self, name):
        self.calls.append((name, self.publisher.is_activated))
        result = self.results.get(name, SUCCESS)
        if isinstance(result, Exception):
            raise result
        return result

    def handle_configure(self, state):
        return self._record('configure')

    def handle_activate(self, state):
        return self._record('activate')

    def handle_deactivate(self, state):
        return self._record('deactivate')

    def handle_cleanup(self, state):
        return self._record('cleanup')

    def handle_shutdown(self, state):
        return self._record('shutdown')

    def handle_error(self, state):
        return self._record('error')


@pytest.fixture(autouse=True)
def ros_context():
    rclpy.init()
    yield
    rclpy.shutdown()


@pytest.fixture
def make_node():
    nodes = []

    def make(**kwargs):
        nodes.append(RecordingNode(**kwargs))
        return nodes[-1]

    yield make
    for node in nodes:
        node.destroy_node()


def test_publisher_is_a_lifecycle_publisher(make_node):
    assert isinstance(make_node().publisher, LifecyclePublisher)


def test_default_hooks_succeed():
    class Plain(LifecycleNode):
        pass

    node = Plain('plain_node')
    try:
        assert SUCCESS == node.trigger_configure()
        assert SUCCESS == node.trigger_activate()
        assert SUCCESS == node.trigger_deactivate()
        assert SUCCESS == node.trigger_cleanup()
        assert SUCCESS == node.trigger_configure()
        assert SUCCESS == node.trigger_shutdown()
    finally:
        node.destroy_node()


def test_each_hook_runs_once_in_order(make_node):
    node = make_node()
    assert SUCCESS == node.trigger_configure()
    assert SUCCESS == node.trigger_activate()
    assert SUCCESS == node.trigger_deactivate()
    assert SUCCESS == node.trigger_cleanup()
    assert [('configure', False), ('activate', True), ('deactivate', True), ('cleanup', False)] == node.calls


def test_publisher_is_active_after_activate_and_not_after_deactivate(make_node):
    node = make_node()
    node.trigger_configure()
    assert not node.publisher.is_activated
    node.trigger_activate()
    assert node.publisher.is_activated
    node.trigger_deactivate()
    assert not node.publisher.is_activated


@pytest.mark.parametrize(
    'result, state',
    [(FAILURE, 'inactive'), (ERROR, 'unconfigured'), (RuntimeError('fixture failure'), 'unconfigured')],
    ids=['failure', 'error', 'raise'],
)
def test_unsuccessful_activate_leaves_publisher_inactive(make_node, result, state):
    node = make_node(results={'activate': result})
    node.trigger_configure()
    assert SUCCESS != node.trigger_activate()
    assert not node.publisher.is_activated
    assert state == node._state_machine.current_state[1]


def test_failed_deactivate_keeps_publisher_active(make_node):
    node = make_node(results={'deactivate': FAILURE})
    node.trigger_configure()
    node.trigger_activate()
    assert FAILURE == node.trigger_deactivate()
    assert node.publisher.is_activated
    assert 'active' == node._state_machine.current_state[1]


def test_shutdown_from_active_deactivates_before_the_hook(make_node):
    node = make_node()
    node.trigger_configure()
    node.trigger_activate()
    assert SUCCESS == node.trigger_shutdown()
    assert not node.publisher.is_activated
    assert ('shutdown', False) == node.calls[-1]


def test_error_deactivates_before_the_hook(make_node):
    node = make_node(results={'activate': RuntimeError('fixture failure')})
    node.trigger_configure()
    node.trigger_activate()
    assert ('error', False) == node.calls[-1]
    assert not node.publisher.is_activated


def test_error_from_active_deactivates(make_node):
    node = make_node(results={'deactivate': RuntimeError('fixture failure')})
    node.trigger_configure()
    node.trigger_activate()
    node.trigger_deactivate()
    assert ('error', False) == node.calls[-1]
    assert not node.publisher.is_activated


class GateRecordingNode(LifecycleNode):
    """Record whether the activation gate is open in each hook."""

    def __init__(self, activate_result=SUCCESS):
        super().__init__('gate_recording_node')
        self.activate_result = activate_result
        self.gate_open_in = {}

    def _record(self, name):
        self.gate_open_in[name] = self.activation_gate.is_activated
        return SUCCESS

    def handle_configure(self, state):
        return self._record('configure')

    def handle_activate(self, state):
        self._record('activate')
        return self.activate_result

    def handle_deactivate(self, state):
        return self._record('deactivate')

    def handle_shutdown(self, state):
        return self._record('shutdown')


@pytest.fixture
def gate_node():
    nodes = []

    def make(**kwargs):
        nodes.append(GateRecordingNode(**kwargs))
        return nodes[-1]

    yield make
    for node in nodes:
        node.destroy_node()


def test_gate_opens_before_handle_activate_and_closes_after_handle_deactivate(gate_node):
    node = gate_node()
    assert not node.activation_gate.is_activated
    node.trigger_configure()
    assert not node.activation_gate.is_activated
    node.trigger_activate()
    assert node.activation_gate.is_activated
    node.trigger_deactivate()
    assert not node.activation_gate.is_activated
    assert {'configure': False, 'activate': True, 'deactivate': True} == node.gate_open_in


def test_gate_is_closed_after_a_failed_activate(gate_node):
    node = gate_node(activate_result=FAILURE)
    node.trigger_configure()
    node.trigger_activate()
    assert not node.activation_gate.is_activated


def test_gate_is_closed_in_shutdown_from_active(gate_node):
    node = gate_node()
    node.trigger_configure()
    node.trigger_activate()
    node.trigger_shutdown()
    assert not node.gate_open_in['shutdown']
    assert not node.activation_gate.is_activated


def test_gate_is_read_only(gate_node):
    node = gate_node()
    with pytest.raises(AttributeError):
        node.activation_gate = SimpleManagedEntity()


@pytest.mark.parametrize('callback', [f'on_{hook}' for hook in HOOKS])
def test_defining_a_transition_callback_raises(callback):
    namespace = {callback: lambda self, state: SUCCESS}
    with pytest.raises(TypeError, match=f'{callback}.*handle_{callback.removeprefix("on_")}'):
        type('Overriding', (LifecycleNode,), namespace)


def test_transition_callback_is_rejected_in_an_indirect_subclass():
    class Base(LifecycleNode):
        pass

    with pytest.raises(TypeError, match='on_activate'):
        type('Indirect', (Base,), {'on_activate': lambda self, state: SUCCESS})


def test_hooks_may_be_overridden_in_an_indirect_subclass():
    class Base(LifecycleNode):
        def handle_activate(self, state):
            return FAILURE

    class Derived(Base):
        def handle_activate(self, state):
            return SUCCESS

    assert Derived.handle_activate is not Base.handle_activate


def test_run_node_configures_and_activates_a_subclass(run_script):
    node = run_script(EXAMPLES_DIR / 'lifecycle_node.py')
    node.wait_ready('Configured')
    node.wait_ready('Activated')
    node.wait_ready('Publishing')
    code, output = node.stop(signal.SIGINT)
    assert 0 == code, output
    assert 'Shut down' in output
