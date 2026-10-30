# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Check which generated documents are registered with the ament index, and that ``local://`` includes are rewritten."""

from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from ament_index_python.resources import get_resource, get_resources
from conftest import PACKAGE

from nodl_schema import load_nodl


def _registered_resources() -> set[str]:
    return {name.removeprefix(f'{PACKAGE}__') for name in get_resources('nodl') if name.startswith(f'{PACKAGE}__')}


def test_documents_are_registered_under_their_target_names_or_overrides():
    assert {'echo_node_base', 'lifecycle_node', 'status_mixin', 'composed_node_base'} == _registered_resources()


def test_no_index_document_is_not_registered():
    assert 'unindexed_echo_node_base' not in _registered_resources()


def test_document_with_resource_name_is_not_registered_under_its_target():
    assert 'lifecycle_node_base' not in _registered_resources()
    assert 'status_mixin_base' not in _registered_resources()


def test_registered_document_keeps_its_entities_and_includes():
    document, _ = get_resource('nodl', f'{PACKAGE}__lifecycle_node')

    assert 'nodl://nodl_common_interfaces/lifecycle_node' in document
    assert 'name: /lifecycle_status' in document


def test_local_include_is_rewritten_to_the_registered_name():
    document, _ = get_resource('nodl', f'{PACKAGE}__composed_node_base')

    assert f'nodl://{PACKAGE}/status_mixin' in document
    assert 'local://' not in document


def test_document_is_installed_in_the_package_share_directory():
    share = Path(get_package_share_directory(PACKAGE)) / 'nodl'

    assert {
        'echo_node_base.nodl.yaml',
        'lifecycle_node.nodl.yaml',
        'status_mixin.nodl.yaml',
        'composed_node_base.nodl.yaml',
    } == {path.name for path in share.iterdir()}


def test_registered_documents_resolve_through_the_index(tmp_path):
    source = tmp_path / 'downstream.nodl.yaml'
    source.write_text(f'nodl_version: 2\ninclude:\n  - ref: nodl://{PACKAGE}/composed_node_base\n')

    document = load_nodl(source)

    assert ['/status'] == [publisher.name for publisher in document.publishers]
    assert ['/composed_in'] == [subscription.name for subscription in document.subscriptions]
