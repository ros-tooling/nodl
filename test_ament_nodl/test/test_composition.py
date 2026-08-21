# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""End-to-end composition test: resolve a nodl:// include through the real ament index.

These check that the reference form lines up with what registration installs, which a fake
resolver cannot show. The documents registered here are declared in CMakeLists.txt.

Including documents are authored in the tests rather than registered.
A nodl:// reference reads the installed workspace, so a document cannot reference its own
package at build time, before that package is installed.
"""

import pytest
from ament_index_python.resources import get_resource

from nodl_schema import load_nodl
from nodl_schema.composition import MergeError, ResolutionError

_LOCAL_SUBSCRIPTION = (
    'subscriptions:\n'
    '  - name: /local_input\n'
    '    type: std_msgs/msg/String\n'
    '    qos: {history: SYSTEM_DEFAULT, reliability: SYSTEM_DEFAULT}\n'
)


def test_nodl_include_resolves_from_ament_index(tmp_path):
    doc_path = tmp_path / 'test.nodl.yaml'
    doc_path.write_text(f'nodl_version: 2\n{_LOCAL_SUBSCRIPTION}include:\n  - ref: nodl://test_ament_nodl/basic_node\n')
    # basic_node contributes a /chatter publisher; the including document adds its own subscription.
    doc = load_nodl(doc_path)
    assert doc.publishers
    assert [p.name for p in doc.publishers] == ['/chatter']
    assert doc.subscriptions
    assert [s.name for s in doc.subscriptions] == ['/local_input']
    # The include key is consumed once resolved.
    assert doc.include is None


def test_included_qos_survives_the_round_trip(tmp_path):
    # The included document is fetched as text and reparsed, so its details must survive.
    source = tmp_path / 'test.nodl.yaml'
    source.write_text('nodl_version: 2\ninclude:\n  - ref: nodl://test_ament_nodl/basic_node\n')
    doc = load_nodl(source)
    assert doc.publishers
    qos = doc.publishers[0].qos
    assert qos.depth == 10
    assert qos.history.value == 'KEEP_LAST'
    assert qos.reliability.value == 'RELIABLE'


def test_include_follows_the_package_override_in_the_resource_key(tmp_path):
    # custom_exe is registered with PACKAGE custom_pkg, so the URI must name custom_pkg.
    # It declares no entities, so this asserts only that the lookup found it.
    source = tmp_path / 'custom_pkg.nodl.yaml'
    source.write_text('nodl_version: 2\ninclude:\n  - ref: nodl://custom_pkg/custom_exe\n')
    doc = load_nodl(source)
    assert doc.include is None

    # The same name under this package is a different key, and nothing registered it.
    missing = tmp_path / 'missing.nodl.yaml'
    missing.write_text('nodl_version: 2\ninclude:\n  - ref: nodl://test_ament_nodl/custom_exe\n')
    with pytest.raises(ResolutionError):
        load_nodl(missing)


def test_include_resolves_a_json_document(tmp_path):
    # The index holds text, so the frontend the author used does not reach the consumer.
    source = tmp_path / 'test.nodl.yaml'
    source.write_text('nodl_version: 2\ninclude:\n  - ref: nodl://test_ament_nodl/json_node\n')
    doc = load_nodl(source)
    assert doc.include is None


def test_collision_with_an_included_document_raises(tmp_path):
    # basic_node publishes /chatter, so publishing it here too is a duplicate.
    source = tmp_path / 'test.nodl.yaml'
    source.write_text(
        'nodl_version: 2\n'
        'publishers:\n'
        '  - name: /chatter\n'
        '    type: std_msgs/msg/String\n'
        '    qos: {history: SYSTEM_DEFAULT, reliability: SYSTEM_DEFAULT}\n'
        'include:\n  - ref: nodl://test_ament_nodl/basic_node\n'
    )
    with pytest.raises(MergeError, match='/chatter'):
        load_nodl(source)


def test_unresolvable_nodl_include_raises(tmp_path):
    source = tmp_path / 'test.nodl.yaml'
    source.write_text('nodl_version: 2\ninclude:\n  - ref: nodl://test_ament_nodl/no_such_node\n')
    with pytest.raises(ResolutionError, match='nodl://test_ament_nodl/no_such_node'):
        load_nodl(source)


def test_no_resolve_leaves_the_include_untouched(tmp_path):
    source = tmp_path / 'test.nodl.yaml'
    source.write_text('nodl_version: 2\ninclude:\n  - ref: nodl://test_ament_nodl/no_such_node\n')
    doc = load_nodl(source, resolve=False)
    assert doc.include
    assert doc.include[0].ref == 'nodl://test_ament_nodl/no_such_node'


def test_registered_document_is_installed_as_authored():
    # Registration does not rewrite, so a consumer resolves the document as authored.
    content, _ = get_resource('nodl', 'test_ament_nodl__basic_node')
    assert 'include' not in content
    assert '/chatter' in content
