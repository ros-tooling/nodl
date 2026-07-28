# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""End-to-end composition test: resolve a nodl:// include through the real ament index.

The macro registers ``basic_node`` under ``nodl_nodes/test_ament_nodl__basic_node`` (see
CMakeLists.txt). Here we author a document that includes it via ``nodl://`` and confirm the
default resolver finds it in the installed index and merges its entities. This exercises the
resolver + ament index + merge path against real registrations, post-install.
"""

import pytest

from nodl_schema import load_nodl
from nodl_schema.composition import CompositionError


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
