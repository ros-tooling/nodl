# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""End-to-end composition test: resolve a nodl:// include through the real ament index.

The unit tests in nodl_schema drive resolution through a fake resolver, which says nothing about
whether the reference form actually lines up with what registration installs. Here the macro has
registered basic_node under nodl_nodes/test_ament_nodl__basic_node (see CMakeLists.txt), and we
author a document that includes it by URI, so the resolver, the index, and the merge are exercised
against a real registration.

The including document is authored here rather than registered in CMakeLists.txt on purpose. A
nodl:// reference resolves through the installed workspace, so a document in this package cannot
reference this package at build time, before it is installed. Composing a package's own documents
needs a reference form that reads the source tree, which is a separate change.
"""

import pytest
from ament_index_python.resources import get_resource

from nodl_schema import load_nodl
from nodl_schema.composition import CompositionError

_LOCAL_SUBSCRIPTION = (
    'subscriptions:\n'
    '  - name: /local_input\n'
    '    type: std_msgs/msg/String\n'
    '    qos: {history: SYSTEM_DEFAULT, reliability: SYSTEM_DEFAULT}\n'
)


def test_nodl_include_resolves_from_ament_index():
    # basic_node contributes a /chatter publisher; the including document adds its own subscription.
    doc = load_nodl(f'nodl_version: 2\n{_LOCAL_SUBSCRIPTION}include:\n  - ref: nodl://test_ament_nodl/basic_node\n')
    assert [p.name for p in doc.publishers] == ['/chatter']
    assert [s.name for s in doc.subscriptions] == ['/local_input']
    # The include key is consumed once resolved.
    assert doc.include is None


def test_included_qos_survives_the_round_trip():
    # The included document is fetched as text and reparsed, so its details have to come back intact.
    doc = load_nodl('nodl_version: 2\ninclude:\n  - ref: nodl://test_ament_nodl/basic_node\n')
    qos = doc.publishers[0].qos
    assert qos.depth == 10
    assert qos.history.value == 'KEEP_LAST'
    assert qos.reliability.value == 'RELIABLE'


def test_include_follows_the_package_override_in_the_resource_key():
    # custom_exe is registered with PACKAGE custom_pkg, so the URI has to name custom_pkg. The
    # fixture declares no entities, so what this asserts is that the lookup found it at all.
    doc = load_nodl('nodl_version: 2\ninclude:\n  - ref: nodl://custom_pkg/custom_exe\n')
    assert doc.include is None

    # The same name under the building package is a different key, and nothing registered it.
    with pytest.raises(CompositionError):
        load_nodl('nodl_version: 2\ninclude:\n  - ref: nodl://test_ament_nodl/custom_exe\n')


def test_include_resolves_a_json_document():
    # What the index holds is text, so the frontend the author used does not reach the consumer.
    doc = load_nodl('nodl_version: 2\ninclude:\n  - ref: nodl://test_ament_nodl/json_node\n')
    assert doc.include is None


def test_collision_with_an_included_document_raises():
    # basic_node publishes /chatter, so publishing it here too is a duplicate.
    source = (
        'nodl_version: 2\n'
        'publishers:\n'
        '  - name: /chatter\n'
        '    type: std_msgs/msg/String\n'
        '    qos: {history: SYSTEM_DEFAULT, reliability: SYSTEM_DEFAULT}\n'
        'include:\n  - ref: nodl://test_ament_nodl/basic_node\n'
    )
    with pytest.raises(CompositionError, match='/chatter'):
        load_nodl(source)


def test_unresolvable_nodl_include_raises():
    with pytest.raises(CompositionError, match='nodl://test_ament_nodl/no_such_node'):
        load_nodl('nodl_version: 2\ninclude:\n  - ref: nodl://test_ament_nodl/no_such_node\n')


def test_no_resolve_leaves_the_include_untouched():
    doc = load_nodl(
        'nodl_version: 2\ninclude:\n  - ref: nodl://test_ament_nodl/no_such_node\n',
        resolve=False,
    )
    assert doc.include[0].ref == 'nodl://test_ament_nodl/no_such_node'


def test_registered_document_is_installed_as_authored():
    # Registration does not rewrite anything, so what a consumer resolves is the authored document.
    content, _ = get_resource('nodl_nodes', 'test_ament_nodl__basic_node')
    assert 'include' not in content
    assert '/chatter' in content
