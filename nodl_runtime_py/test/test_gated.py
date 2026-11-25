# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Tests of Gated."""

import pytest
import rclpy
from lifecycle_msgs.srv import GetState
from rclpy.lifecycle import TransitionCallbackReturn as Result

from nodl_runtime_py import Gated, Managed
from nodl_runtime_py.lifecycle import LifecycleNode

SUCCESS = Result.SUCCESS
FAILURE = Result.FAILURE
ERROR = Result.ERROR


class GatedNode(LifecycleNode):
    """A node whose client is handed out only while it is active, and that records what each hook saw."""

    def __init__(self):
        super().__init__('gated_node')
        self.client = self.create_client(GetState, 'peer/get_state')
        self.gated = Gated(self, self.client)
        self.seen = []
        self.results = {}

    def _hook(self, hook):
        self.seen.append((hook, self.gated.get() is not None))
        result = self.results.get(hook, SUCCESS)
        if isinstance(result, Exception):
            raise result
        return result

    def handle_activate(self, state):
        return self._hook('activate')

    def handle_deactivate(self, state):
        return self._hook('deactivate')

    def handle_shutdown(self, state):
        return self._hook('shutdown')

    def handle_error(self, state):
        return self._hook('error')


@pytest.fixture
def node():
    rclpy.init()
    node = GatedNode()
    try:
        yield node
    finally:
        node.destroy_node()
        rclpy.shutdown()


def activate(node):
    assert SUCCESS == node.trigger_configure()
    assert SUCCESS == node.trigger_activate()
    node.seen.clear()


def test_get_is_none_before_activation(node):
    assert node.gated.get() is None
    assert SUCCESS == node.trigger_configure()
    assert node.gated.get() is None


def test_get_returns_the_entity_in_handle_activate_and_while_active(node):
    assert SUCCESS == node.trigger_configure()
    assert SUCCESS == node.trigger_activate()
    assert [('activate', True)] == node.seen
    assert node.client is node.gated.get()


def test_get_returns_the_entity_in_handle_deactivate_and_none_after(node):
    activate(node)
    assert SUCCESS == node.trigger_deactivate()
    assert [('deactivate', True)] == node.seen
    assert node.gated.get() is None


def test_get_returns_the_entity_again_after_reactivation(node):
    activate(node)
    assert SUCCESS == node.trigger_deactivate()
    assert SUCCESS == node.trigger_activate()
    assert node.client is node.gated.get()


def test_a_failing_deactivation_keeps_the_entity(node):
    activate(node)
    node.results['deactivate'] = FAILURE
    assert FAILURE == node.trigger_deactivate()
    assert node.client is node.gated.get()


@pytest.mark.parametrize('failure', [FAILURE, ERROR, RuntimeError('hook failure')], ids=['failure', 'error', 'raise'])
def test_get_is_none_after_a_failed_activation(node, failure):
    assert SUCCESS == node.trigger_configure()
    node.results['activate'] = failure
    node.trigger_activate()
    assert [('activate', True)] == node.seen[:1]
    assert node.gated.get() is None


def test_get_is_none_in_handle_shutdown_from_active(node):
    activate(node)
    assert SUCCESS == node.trigger_shutdown()
    assert [('deactivate', True), ('shutdown', False)] == node.seen
    assert node.gated.get() is None


def test_get_is_none_in_handle_error_from_active(node):
    activate(node)
    node.results['deactivate'] = RuntimeError('hook failure')
    assert ERROR == node.trigger_deactivate()
    assert [('deactivate', True), ('error', False)] == node.seen
    assert node.gated.get() is None


def test_construction_while_active_raises(node):
    activate(node)
    with pytest.raises(RuntimeError, match='not active'):
        Gated(node, node.client)


def test_construction_while_activating_raises(node):
    assert SUCCESS == node.trigger_configure()
    node.add_activation_slot(lambda: Gated(node, node.client), lambda: None)
    assert ERROR == node.trigger_activate()
    assert node.gated.get() is None


def test_gated_and_managed_members_register_in_construction_order(node):
    events = []
    Managed(node, lambda: events.append('managed') or object(), lambda entity: None)
    Gated(node, object())
    node.add_activation_slot(lambda: events.append(f'slot sees {node.gated.get() is not None}'), lambda: None)
    activate(node)
    assert ['managed', 'slot sees True'] == events
