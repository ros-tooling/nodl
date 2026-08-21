# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Verify that tutorial documents are installed and registered unchanged."""

from pathlib import Path

import pytest
from ament_index_python.packages import get_package_share_directory
from ament_index_python.resources import get_resource

PACKAGE = 'nodl_tutorial_verification'
DOCUMENTS = ('talker', 'dummy_laser')


@pytest.mark.parametrize('name', DOCUMENTS)
def test_registered_document_matches_installed_source(name):
    content, prefix = get_resource('nodl_nodes', f'{PACKAGE}__{name}')

    assert prefix
    installed = Path(get_package_share_directory(PACKAGE)) / 'nodl' / f'{name}.nodl.yaml'
    assert installed.read_text() == content


@pytest.mark.parametrize('name', DOCUMENTS)
def test_registered_document_is_nodl_v2(name):
    content, _ = get_resource('nodl_nodes', f'{PACKAGE}__{name}')

    assert 'nodl_version: 2' in content
