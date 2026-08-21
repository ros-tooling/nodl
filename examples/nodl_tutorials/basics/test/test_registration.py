# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Verify that the tutorial document is installed and registered unchanged."""

from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from ament_index_python.resources import get_resource

PACKAGE = 'nodl_tutorial_basics'
DOCUMENT = 'talker'


def test_registered_document_matches_installed_source():
    content, prefix = get_resource('nodl', f'{PACKAGE}__{DOCUMENT}')

    assert prefix
    installed = Path(get_package_share_directory(PACKAGE)) / 'nodl' / f'{DOCUMENT}.nodl.yaml'
    assert installed.read_text() == content


def test_registered_document_is_nodl_v2():
    content, _ = get_resource('nodl', f'{PACKAGE}__{DOCUMENT}')

    assert 'nodl_version: 2' in content
