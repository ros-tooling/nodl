# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Verify registration and transitive lifecycle composition."""

from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from ament_index_python.resources import get_resource

from nodl_schema import load_nodl

PACKAGE = 'controller_server_nodl'


def _installed(document):
    return Path(get_package_share_directory(PACKAGE)) / 'nodl' / f'{document}.nodl.yaml'


def test_registered_document_matches_installed_source():
    content, prefix = get_resource('nodl', f'{PACKAGE}__controller_server')

    assert prefix
    assert _installed('controller_server').read_text() == content


def test_controller_contract_resolves_server_and_lifecycle_interfaces():
    document = load_nodl(_installed('controller_server'))

    assert document.include is None
    assert {(item.name, item.type) for item in document.action_servers or []} == {
        ('follow_path', 'nav2_msgs/action/FollowPath'),
    }
    assert {(item.name, item.type) for item in document.subscriptions or []} == {
        ('speed_limit', 'nav2_msgs/msg/SpeedLimit'),
    }
    assert ('transition_event', 'lifecycle_msgs/msg/TransitionEvent') in {
        (item.name, item.type) for item in document.publishers or []
    }
    assert ('~/change_state', 'lifecycle_msgs/srv/ChangeState') in {
        (item.name, item.type) for item in document.service_servers or []
    }
