# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""End-to-end composition test: resolve a nodl:// include through the real ament index.

The macro registers ``basic_node`` under ``nodl_nodes/test_ament_nodl__basic_node`` (see
CMakeLists.txt). Here we author a document that includes it via ``nodl://`` and confirm the
default resolver finds it in the installed index and merges its entities. This exercises the
resolver + ament index + merge path against real registrations, post-install.
"""

from pathlib import Path

import pytest
from ament_index_python.packages import get_package_share_directory
from ament_index_python.resources import get_resource

from nodl_schema import load_nodl
from nodl_schema.composition import CompositionError


def _share(pkg: str = 'test_ament_nodl') -> Path:
    return Path(get_package_share_directory(pkg))


def test_nodl_include_resolves_from_ament_index():
    # basic_node contributes a /chatter publisher; the including doc adds its own subscription.
    doc = load_nodl(
        'nodl_version: 2\n'
        'subscriptions:\n'
        '  - name: /local_input\n'
        '    type: std_msgs/msg/String\n'
        '    qos: {history: SYSTEM_DEFAULT, reliability: SYSTEM_DEFAULT}\n'
        'include:\n'
        '  - ref: nodl://test_ament_nodl/basic_node\n'
    )
    assert any(p.name == '/chatter' for p in doc.publishers)
    assert any(s.name == '/local_input' for s in doc.subscriptions)
    # The include key is consumed once resolved.
    assert doc.include is None


def test_unresolvable_nodl_include_raises():
    with pytest.raises(CompositionError, match='nodl://test_ament_nodl/no_such_node'):
        load_nodl(
            'nodl_version: 2\ninclude:\n  - ref: nodl://test_ament_nodl/no_such_node\n',
        )


def test_no_resolve_leaves_unresolved_include_untouched():
    doc = load_nodl(
        'nodl_version: 2\ninclude:\n  - ref: nodl://test_ament_nodl/no_such_node\n',
        resolve=False,
    )
    assert doc.include[0].ref == 'nodl://test_ament_nodl/no_such_node'


# ---------------------------------------------------------------------------
# Relative includes, post-install
# ---------------------------------------------------------------------------
#
# composed_node.nodl.yaml is authored with ``ref: common/telemetry.nodl.yaml``. A consumer reading
# it back out of the index gets text and nothing else, so that path would have nothing to resolve
# against. Registration therefore rewrites it to the name telemetry was registered under.


def test_installed_document_carries_a_rewritten_reference():
    content, _ = get_resource('nodl_nodes', 'test_ament_nodl__composed_node')
    assert 'nodl://test_ament_nodl/telemetry' in content
    assert 'common/telemetry.nodl.yaml' not in content


def test_share_copy_is_rewritten_too():
    # Both install destinations get the rewritten document, so the two agree.
    share_copy = (_share() / 'nodl' / 'composed_node.nodl.yaml').read_text()
    content, _ = get_resource('nodl_nodes', 'test_ament_nodl__composed_node')
    assert 'nodl://test_ament_nodl/telemetry' in share_copy
    assert share_copy == content


def test_rewrite_preserves_the_rest_of_the_document():
    # Only the reference changes; everything the author wrote is still there.
    content, _ = get_resource('nodl_nodes', 'test_ament_nodl__composed_node')
    assert 'Node composed from a relative include' in content
    assert '/commands' in content


def test_downstream_consumer_resolves_the_rewritten_reference():
    # The whole point: a consumer with no knowledge of the source layout resolves the chain.
    content, _ = get_resource('nodl_nodes', 'test_ament_nodl__composed_node')
    doc = load_nodl(content)
    assert any(p.name == '/telemetry/heartbeat' for p in doc.publishers)
    assert any(s.name == '/commands' for s in doc.subscriptions)
    assert doc.include is None


def test_referenced_document_is_registered_in_its_own_right():
    content, _ = get_resource('nodl_nodes', 'test_ament_nodl__telemetry')
    assert 'Shared telemetry surface' in content


def test_document_without_relative_refs_is_installed_unchanged():
    # Only documents that actually have something to rewrite are re-serialized.
    content, _ = get_resource('nodl_nodes', 'test_ament_nodl__basic_node')
    assert content == (_share() / 'nodl' / 'basic_node.nodl.yaml').read_text()
