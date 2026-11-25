# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Tests of the activation registry of LifecycleNode and of Managed."""

import threading
import time
import uuid

import pytest
import rclpy
from lifecycle_msgs.msg import Transition
from lifecycle_msgs.srv import ChangeState
from rclpy.executors import MultiThreadedExecutor, SingleThreadedExecutor
from rclpy.lifecycle import TransitionCallbackReturn as Result
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from std_msgs.msg import String

from nodl_runtime_py import Managed
from nodl_runtime_py.lifecycle import LifecycleNode

SUCCESS = Result.SUCCESS
FAILURE = Result.FAILURE
ERROR = Result.ERROR

TIMEOUT_S = 10
LATCHED = QoSProfile(depth=1, reliability=ReliabilityPolicy.RELIABLE, durability=DurabilityPolicy.TRANSIENT_LOCAL)


class RegistryNode(LifecycleNode):
    """Records the creation and destruction of slots and the hooks in one list, and returns or raises what the test sets."""

    def __init__(self, name='registry_node'):
        super().__init__(name)
        self.events = []
        self.results = {}
        self.creators = {}

    def add_slot(self, name):
        """Register a slot that records `name`, and raises when `creators[name]` holds an exception."""

        def create():
            failure = self.creators.get(name)
            if failure is not None:
                raise failure
            self.events.append(f'create {name}')

        return self.add_activation_slot(create, lambda: self.events.append(f'destroy {name}'))

    def _hook(self, hook):
        self.events.append(hook)
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
def rclpy_context():
    rclpy.init()
    try:
        yield
    finally:
        rclpy.shutdown()


@pytest.fixture
def node(rclpy_context):
    node = RegistryNode()
    node.add_slot('a')
    node.add_slot('b')
    node.add_slot('c')
    try:
        yield node
    finally:
        node.destroy_node()


def activate(node):
    assert SUCCESS == node.trigger_configure()
    assert SUCCESS == node.trigger_activate()
    node.events.clear()


def state_label(node):
    return node._state_machine.current_state[1]


CREATED = ['create a', 'create b', 'create c']
DESTROYED = ['destroy c', 'destroy b', 'destroy a']


def test_slots_are_created_in_order_before_handle_activate(node):
    assert SUCCESS == node.trigger_configure()
    assert [] == node.events
    assert SUCCESS == node.trigger_activate()
    assert [*CREATED, 'activate'] == node.events


def test_slots_are_destroyed_in_reverse_after_handle_deactivate(node):
    activate(node)
    assert SUCCESS == node.trigger_deactivate()
    assert ['deactivate', *DESTROYED] == node.events


def test_slots_are_created_again_on_reactivation(node):
    activate(node)
    assert SUCCESS == node.trigger_deactivate()
    node.events.clear()
    assert SUCCESS == node.trigger_activate()
    assert [*CREATED, 'activate'] == node.events


def test_a_failing_handle_deactivate_keeps_the_slots(node):
    activate(node)
    node.results['deactivate'] = FAILURE
    assert FAILURE == node.trigger_deactivate()
    assert ['deactivate'] == node.events


@pytest.mark.parametrize('failure', [FAILURE, ERROR, RuntimeError('hook failure')], ids=['failure', 'error', 'raise'])
def test_a_failed_activation_destroys_the_slots(node, failure):
    assert SUCCESS == node.trigger_configure()
    node.results['activate'] = failure
    node.trigger_activate()
    expected = [*CREATED, 'activate', *DESTROYED]
    if FAILURE != failure:
        expected.append('error')
    assert expected == node.events


def test_shutdown_from_active_destroys_the_slots_before_handle_shutdown(node):
    activate(node)
    assert SUCCESS == node.trigger_shutdown()
    assert ['deactivate', *DESTROYED, 'shutdown'] == node.events


def test_shutdown_from_inactive_destroys_no_slot(node):
    assert SUCCESS == node.trigger_configure()
    assert SUCCESS == node.trigger_shutdown()
    assert ['shutdown'] == node.events


def test_error_from_active_destroys_the_slots_before_handle_error(node):
    activate(node)
    node.results['deactivate'] = RuntimeError('hook failure')
    assert ERROR == node.trigger_deactivate()
    assert ['deactivate', *DESTROYED, 'error'] == node.events


def test_error_from_active_after_an_error_result_destroys_the_slots_once(node):
    activate(node)
    node.results['deactivate'] = ERROR
    assert ERROR == node.trigger_deactivate()
    assert ['deactivate', 'deactivate', *DESTROYED, 'error'] == node.events


def test_a_raising_creator_rolls_back_the_slots_created_before_it(node):
    assert SUCCESS == node.trigger_configure()
    node.creators['c'] = RuntimeError('creator failure')
    assert ERROR == node.trigger_activate()
    assert ['create a', 'create b', 'destroy b', 'destroy a', 'error'] == node.events
    assert 'unconfigured' == state_label(node)


def test_the_slots_are_created_again_after_a_rollback(node):
    assert SUCCESS == node.trigger_configure()
    node.creators['c'] = RuntimeError('creator failure')
    assert ERROR == node.trigger_activate()
    node.creators.clear()
    node.events.clear()
    assert SUCCESS == node.trigger_configure()
    assert SUCCESS == node.trigger_activate()
    assert [*CREATED, 'activate'] == node.events


def test_a_raising_destroyer_is_logged_and_the_others_still_run(node):
    node.add_activation_slot(lambda: node.events.append('create d'), lambda: 1 / 0)
    activate(node)
    assert SUCCESS == node.trigger_deactivate()
    assert ['deactivate', *DESTROYED] == node.events


def test_a_slot_registered_while_inactive_is_created_at_the_next_activation(node):
    activate(node)
    assert SUCCESS == node.trigger_deactivate()
    node.add_slot('d')
    node.events.clear()
    assert SUCCESS == node.trigger_activate()
    assert [*CREATED, 'create d', 'activate'] == node.events


def test_registering_while_active_raises(node):
    activate(node)
    with pytest.raises(RuntimeError, match='not active'):
        node.add_slot('late')
    with pytest.raises(RuntimeError, match='not active'):
        Managed(node, lambda: object(), lambda entity: None)


def test_registering_while_activating_raises(node):
    assert SUCCESS == node.trigger_configure()
    node.add_activation_slot(lambda: node.add_slot('late'), lambda: None)
    assert ERROR == node.trigger_activate()
    assert ['create a', 'create b', 'create c', 'destroy c', 'destroy b', 'destroy a', 'error'] == node.events


def test_registering_is_allowed_again_after_deactivation(node):
    activate(node)
    assert SUCCESS == node.trigger_deactivate()
    node.add_slot('late')


def test_managed_creates_and_destroys_its_entity(rclpy_context):
    node = RegistryNode()
    events = []
    entity = object()
    managed = Managed(node, lambda: events.append('create') or entity, lambda e: events.append(('destroy', e)))
    assert not managed
    assert SUCCESS == node.trigger_configure()
    assert not managed
    assert SUCCESS == node.trigger_activate()
    assert managed
    assert ['create'] == events
    assert SUCCESS == node.trigger_deactivate()
    assert not managed
    assert ['create', ('destroy', entity)] == events
    node.destroy_node()


def test_managed_members_register_in_construction_order(rclpy_context):
    node = RegistryNode()
    events = []
    for name in ('first', 'second'):
        Managed(node, lambda name=name: events.append(f'create {name}'), lambda e: None)
    assert SUCCESS == node.trigger_configure()
    assert SUCCESS == node.trigger_activate()
    assert ['create first', 'create second'] == events
    node.destroy_node()


class SubscribingNode(LifecycleNode):
    """Receives strings through a transient local subscription that exists only while active."""

    def __init__(self, name, topic):
        super().__init__(name)
        self.received = []
        self.sub = Managed(
            self,
            lambda: self.create_subscription(String, topic, lambda msg: self.received.append(msg.data), LATCHED),
            self.destroy_subscription,
        )


def spin_until(executor, condition, timeout_s=TIMEOUT_S):
    """Spin `executor` until `condition()` is true, and return whether it became true."""
    deadline = time.monotonic() + timeout_s
    while not condition():
        if time.monotonic() > deadline:
            return False
        executor.spin_once(timeout_sec=0.05)
    return True


def test_a_subscription_is_in_the_graph_only_while_active(rclpy_context):
    topic = f'graph_{uuid.uuid4().hex}'
    node = SubscribingNode('graph_node', topic)
    probe = rclpy.create_node('graph_probe')
    executor = SingleThreadedExecutor()
    executor.add_node(node)
    executor.add_node(probe)
    try:
        # Give discovery time, so that a subscription that is not removed would show.
        assert not spin_until(executor, lambda: probe.count_subscribers(topic) > 0, 1.0)
        assert SUCCESS == node.trigger_configure()
        assert not spin_until(executor, lambda: probe.count_subscribers(topic) > 0, 1.0)
        assert SUCCESS == node.trigger_activate()
        assert spin_until(executor, lambda: 1 == probe.count_subscribers(topic))
        assert SUCCESS == node.trigger_deactivate()
        assert spin_until(executor, lambda: 0 == probe.count_subscribers(topic))
        assert SUCCESS == node.trigger_activate()
        assert spin_until(executor, lambda: 1 == probe.count_subscribers(topic))
    finally:
        executor.shutdown()
        probe.destroy_node()
        node.destroy_node()


def test_a_transient_local_sample_published_before_configure_is_delivered_after_activation(rclpy_context):
    topic = f'latched_{uuid.uuid4().hex}'
    node = SubscribingNode('latched_node', topic)
    publisher_node = rclpy.create_node('latched_publisher')
    publisher = publisher_node.create_publisher(String, topic, LATCHED)
    executor = SingleThreadedExecutor()
    executor.add_node(node)
    executor.add_node(publisher_node)
    try:
        publisher.publish(String(data='before configure'))
        assert SUCCESS == node.trigger_configure()
        assert not spin_until(executor, lambda: node.received, 0.5)
        assert SUCCESS == node.trigger_activate()
        assert spin_until(executor, lambda: node.received)
        assert ['before configure'] == node.received
    finally:
        executor.shutdown()
        publisher_node.destroy_node()
        node.destroy_node()


@pytest.mark.parametrize('executor_class', [SingleThreadedExecutor, MultiThreadedExecutor])
def test_deactivation_through_the_change_state_service_while_spinning(rclpy_context, executor_class):
    topic = f'service_{uuid.uuid4().hex}'
    name = f'service_node_{uuid.uuid4().hex}'
    node = SubscribingNode(name, topic)
    client_node = rclpy.create_node('change_state_client')
    publisher = client_node.create_publisher(String, topic, LATCHED)
    client = client_node.create_client(ChangeState, f'/{name}/change_state')
    executor = executor_class()
    executor.add_node(node)
    client_executor = SingleThreadedExecutor()
    client_executor.add_node(client_node)
    spinner = threading.Thread(target=executor.spin, daemon=True)
    spinner.start()

    def request(transition_id):
        future = client.call_async(ChangeState.Request(transition=Transition(id=transition_id)))
        assert spin_until(client_executor, future.done), f'transition {transition_id} did not complete'
        assert future.result().success, f'transition {transition_id} failed'

    try:
        assert client.wait_for_service(timeout_sec=TIMEOUT_S)
        request(Transition.TRANSITION_CONFIGURE)
        for _ in range(20):
            publisher.publish(String(data='sample'))
            request(Transition.TRANSITION_ACTIVATE)
            assert node.sub
            publisher.publish(String(data='sample'))
            request(Transition.TRANSITION_DEACTIVATE)
            assert not node.sub
        request(Transition.TRANSITION_ACTIVATE)
        request(Transition.TRANSITION_ACTIVE_SHUTDOWN)
        assert not node.sub
    finally:
        executor.shutdown()
        spinner.join(TIMEOUT_S)
        assert not spinner.is_alive()
        client_node.destroy_node()
        node.destroy_node()
