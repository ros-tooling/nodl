# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Verify that the tutorial document is installed and registered unchanged."""

from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from ament_index_python.resources import get_resource

from nodl_schema import load_nodl

PACKAGE = 'nodl_tutorial_dummy_robot'
DOCUMENT = 'dummy_laser'


def test_registered_document_matches_installed_source():
    content, prefix = get_resource('nodl', f'{PACKAGE}__{DOCUMENT}')

    assert prefix
    installed = Path(get_package_share_directory(PACKAGE)) / 'nodl' / f'{DOCUMENT}.nodl.yaml'
    assert installed.read_text() == content


def test_registered_document_declares_the_scan_contract():
    installed = Path(get_package_share_directory(PACKAGE)) / 'nodl' / f'{DOCUMENT}.nodl.yaml'
    document = load_nodl(installed)

    assert document.nodl_version == 2
    assert len(document.publishers) == 1
    publisher = document.publishers[0]
    assert publisher.name == 'scan'
    assert publisher.type == 'sensor_msgs/msg/LaserScan'
    assert publisher.qos.history.value == 'KEEP_LAST'
    assert publisher.qos.depth == 10
    assert publisher.qos.reliability.value == 'RELIABLE'
    assert publisher.qos.durability.value == 'VOLATILE'
