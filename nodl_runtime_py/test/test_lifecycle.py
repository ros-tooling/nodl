# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Tests of the transition order and sealing of LifecycleNode."""

import pytest
import rclpy
from rclpy.lifecycle import LifecycleState
from rclpy.lifecycle import TransitionCallbackReturn as Result
from std_msgs.msg import String

from nodl_runtime_py.lifecycle import LifecycleNode

SUCCESS = Result.SUCCESS
FAILURE = Result.FAILURE
ERROR = Result.ERROR


class RecordingNode(LifecycleNode):
    """Records each hook with whether its lifecycle publisher is active, and returns or raises what the test sets."""

    def __init__(self):
        super().__init__('recording_node')
        self.pub = self.create_lifecycle_publisher(String, 'chatter', 10)
        self.events = []
        self.results = {}

    def _record(self, hook):
        self.events.append((hook, self.pub.is_activated))
        result = self.results.get(hook, SUCCESS)
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


@pytest.fixture
def node():
    rclpy.init()
    node = RecordingNode()
    try:
        yield node
    finally:
        node.destroy_node()
        rclpy.shutdown()


def state_label(node):
    return node._state_machine.current_state[1]


def activate(node):
    assert SUCCESS == node.trigger_configure()
    assert SUCCESS == node.trigger_activate()
    node.events.clear()


def test_configure_activate_deactivate_cleanup_run_the_hooks_in_order(node):
    for trigger in (node.trigger_configure, node.trigger_activate, node.trigger_deactivate, node.trigger_cleanup):
        assert SUCCESS == trigger()
    assert [
        ('configure', False),
        # The publisher is active in handle_activate and in handle_deactivate.
        ('activate', True),
        ('deactivate', True),
        ('cleanup', False),
    ] == node.events
    assert 'unconfigured' == state_label(node)


def test_hooks_default_to_success():
    rclpy.init()
    try:
        plain = LifecycleNode('plain_node')
        for trigger in (
            plain.trigger_configure,
            plain.trigger_activate,
            plain.trigger_deactivate,
            plain.trigger_cleanup,
        ):
            assert SUCCESS == trigger()
        plain.destroy_node()
    finally:
        rclpy.shutdown()


@pytest.mark.parametrize('failure', [FAILURE, ERROR, RuntimeError('hook failure')], ids=['failure', 'error', 'raise'])
def test_failing_handle_activate_leaves_the_publisher_inactive(node, failure):
    assert SUCCESS == node.trigger_configure()
    node.results['activate'] = failure
    node.events.clear()
    node.trigger_activate()
    assert not node.pub.is_activated
    # FAILURE stays inactive, and ERROR runs handle_error, which ends unconfigured.
    expected_events = [('activate', True)] if FAILURE == failure else [('activate', True), ('error', False)]
    assert expected_events == node.events
    assert ('inactive' if FAILURE == failure else 'unconfigured') == state_label(node)


def test_failing_handle_deactivate_leaves_the_node_active(node):
    activate(node)
    node.results['deactivate'] = FAILURE
    assert FAILURE == node.trigger_deactivate()
    assert node.pub.is_activated
    assert 'active' == state_label(node)
    assert [('deactivate', True)] == node.events


def test_raising_handle_deactivate_runs_error_without_running_it_twice(node):
    activate(node)
    node.results['deactivate'] = RuntimeError('hook failure')
    assert ERROR == node.trigger_deactivate()
    assert [('deactivate', True), ('error', False)] == node.events
    assert not node.pub.is_activated
    assert 'unconfigured' == state_label(node)


def test_shutdown_from_active_deactivates_first(node):
    activate(node)
    assert SUCCESS == node.trigger_shutdown()
    assert [('deactivate', True), ('shutdown', False)] == node.events
    assert 'finalized' == state_label(node)


@pytest.mark.parametrize('result', [FAILURE, ERROR, RuntimeError('hook failure')], ids=['failure', 'error', 'raise'])
def test_shutdown_from_active_ignores_the_result_of_handle_deactivate(node, result):
    activate(node)
    node.results['deactivate'] = result
    assert SUCCESS == node.trigger_shutdown()
    assert [('deactivate', True), ('shutdown', False)] == node.events
    assert not node.pub.is_activated
    assert 'finalized' == state_label(node)


@pytest.mark.parametrize(
    'prepare', [lambda node: None, lambda node: node.trigger_configure()], ids=['unconfigured', 'inactive']
)
def test_shutdown_from_inactive_runs_only_the_hook(node, prepare):
    prepare(node)
    node.events.clear()
    assert SUCCESS == node.trigger_shutdown()
    assert [('shutdown', False)] == node.events
    assert 'finalized' == state_label(node)


def test_error_from_active_deactivates_first(node):
    activate(node)
    node.results['shutdown'] = RuntimeError('hook failure')
    assert ERROR == node.trigger_shutdown()
    # handle_deactivate ran for the shutdown, so the error does not run it again.
    assert [('deactivate', True), ('shutdown', False), ('error', False)] == node.events
    assert not node.pub.is_activated
    assert 'unconfigured' == state_label(node)


def test_error_from_active_runs_handle_deactivate_again_after_an_error_result(node):
    activate(node)
    node.results['deactivate'] = ERROR
    node.results['error'] = FAILURE
    assert ERROR == node.trigger_deactivate()
    # Only an exception stops the error transition from running handle_deactivate again, and the result of the second run is ignored.
    assert [('deactivate', True), ('deactivate', True), ('error', False)] == node.events
    assert not node.pub.is_activated
    assert 'finalized' == state_label(node)


def test_error_from_inactive_runs_only_the_hook(node):
    assert SUCCESS == node.trigger_configure()
    node.results['cleanup'] = RuntimeError('hook failure')
    node.events.clear()
    assert ERROR == node.trigger_cleanup()
    assert [('cleanup', False), ('error', False)] == node.events


def test_hooks_run_again_after_reactivation(node):
    activate(node)
    assert SUCCESS == node.trigger_deactivate()
    node.events.clear()
    assert SUCCESS == node.trigger_activate()
    assert SUCCESS == node.trigger_shutdown()
    assert [('activate', True), ('deactivate', True), ('shutdown', False)] == node.events


@pytest.mark.parametrize(
    'name, hook',
    [
        ('on_configure', 'handle_configure'),
        ('on_activate', 'handle_activate'),
        ('on_deactivate', 'handle_deactivate'),
        ('on_cleanup', 'handle_cleanup'),
        ('on_shutdown', 'handle_shutdown'),
        ('on_error', 'handle_error'),
    ],
)
def test_defining_a_transition_callback_raises_type_error_naming_the_hook(name, hook):
    with pytest.raises(TypeError, match=rf'{name}.*Define {hook} instead'):
        type('Sealed', (LifecycleNode,), {name: lambda self, state: SUCCESS})


def test_defining_several_transition_callbacks_names_them_all():
    with pytest.raises(TypeError, match=r'on_activate, on_error.*Define handle_activate, handle_error instead'):
        type(
            'Sealed',
            (LifecycleNode,),
            {'on_activate': lambda self, state: SUCCESS, 'on_error': lambda self, state: SUCCESS},
        )


def test_a_subclass_of_a_subclass_cannot_define_a_transition_callback():
    with pytest.raises(TypeError, match='on_cleanup'):
        type('Sealed', (RecordingNode,), {'on_cleanup': lambda self, state: SUCCESS})


def test_state_is_passed_to_the_hooks():
    rclpy.init()
    try:
        seen = []

        class StateNode(LifecycleNode):
            def handle_activate(self, state):
                seen.append(state)
                return SUCCESS

        node = StateNode('state_node')
        node.trigger_configure()
        node.trigger_activate()
        assert [LifecycleState(state_id=2, label='inactive')] == seen
        node.destroy_node()
    finally:
        rclpy.shutdown()
