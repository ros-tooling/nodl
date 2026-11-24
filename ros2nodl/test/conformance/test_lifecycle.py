# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""The lifecycle detection and the transition sequence of ``activate_node``, with no ROS graph."""

import pytest
from lifecycle_msgs.msg import State, Transition

from nodl_schema.models import NodlDocument, ServiceEndpoint
from ros2nodl.lifecycle import LifecycleError, NodeState, activate_with, declares_lifecycle

_UNCONFIGURED = NodeState(State.PRIMARY_STATE_UNCONFIGURED, 'unconfigured')
_INACTIVE = NodeState(State.PRIMARY_STATE_INACTIVE, 'inactive')
_ACTIVE = NodeState(State.PRIMARY_STATE_ACTIVE, 'active')
_FINALIZED = NodeState(State.PRIMARY_STATE_FINALIZED, 'finalized')


def _document(*servers):
    return NodlDocument(nodl_version=2, service_servers=[ServiceEndpoint(name=n, type=t) for n, t in servers])


class _Node:
    """A lifecycle node that follows its transitions, and fails the ones in ``failing``."""

    def __init__(self, state, failing=()):
        self.state = state
        self.failing = set(failing)
        self.transitions = []

    def get_state(self):
        return self.state

    def change_state(self, transition_id):
        self.transitions.append(transition_id)
        if transition_id in self.failing:
            return False
        self.state = {
            Transition.TRANSITION_CONFIGURE: _INACTIVE,
            Transition.TRANSITION_ACTIVATE: _ACTIVE,
        }[transition_id]
        return True

    def activate(self):
        activate_with('/ns/node', get_state=self.get_state, change_state=self.change_state)


def test_a_document_with_the_change_state_service_is_lifecycle():
    assert declares_lifecycle(_document(('~/change_state', 'lifecycle_msgs/srv/ChangeState')))


def test_the_change_state_type_may_omit_the_interface_kind():
    assert declares_lifecycle(_document(('~/change_state', 'lifecycle_msgs/ChangeState')))


@pytest.mark.parametrize(
    'servers',
    [
        [],
        [('reset', 'std_srvs/srv/Empty')],
        [('~/get_state', 'lifecycle_msgs/srv/GetState')],
        [('~/change_state', 'std_srvs/srv/Empty')],
        [('change_state', 'lifecycle_msgs/srv/ChangeState')],
    ],
)
def test_other_documents_are_not_lifecycle(servers):
    assert not declares_lifecycle(_document(*servers))


def test_a_document_without_service_servers_is_not_lifecycle():
    assert not declares_lifecycle(NodlDocument(nodl_version=2))


def test_an_unconfigured_node_is_configured_then_activated():
    node = _Node(_UNCONFIGURED)

    node.activate()

    assert node.transitions == [Transition.TRANSITION_CONFIGURE, Transition.TRANSITION_ACTIVATE]
    assert node.state == _ACTIVE


def test_an_inactive_node_is_only_activated():
    node = _Node(_INACTIVE)

    node.activate()

    assert node.transitions == [Transition.TRANSITION_ACTIVATE]


def test_an_active_node_is_left_alone():
    node = _Node(_ACTIVE)

    node.activate()

    assert node.transitions == []


def test_a_failed_configure_names_the_node_and_its_state():
    node = _Node(_UNCONFIGURED, failing={Transition.TRANSITION_CONFIGURE})

    with pytest.raises(LifecycleError, match='/ns/node: the configure transition failed, and the node is unconfigured'):
        node.activate()

    assert node.transitions == [Transition.TRANSITION_CONFIGURE]


def test_a_failed_activation_names_the_node_and_its_state():
    node = _Node(_INACTIVE, failing={Transition.TRANSITION_ACTIVATE})

    with pytest.raises(LifecycleError, match='/ns/node: the activate transition failed, and the node is inactive'):
        node.activate()


def test_a_node_in_another_state_is_rejected():
    node = _Node(_FINALIZED)

    with pytest.raises(LifecycleError, match='/ns/node: it is finalized'):
        node.activate()

    assert node.transitions == []
