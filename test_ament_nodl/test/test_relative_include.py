# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""End-to-end test for local:// includes surviving installation.

composed_node.nodl.yaml is authored with ``ref: local://common/telemetry.nodl.yaml``, which is
resolvable only in the source tree. Registration rewrites it to the name telemetry was registered
under, so a consumer reading the document out of the index has something it can resolve.

Both documents are registered in CMakeLists.txt, telemetry first.
"""

from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from ament_index_python.resources import get_resource

from nodl_schema import load_nodl


def _installed(name: str = 'composed_node') -> str:
    content, _ = get_resource('nodl_nodes', f'test_ament_nodl__{name}')
    return content


def _share_copy(filename: str) -> str:
    return (Path(get_package_share_directory('test_ament_nodl')) / 'nodl' / filename).read_text()


def test_installed_document_carries_a_rewritten_reference():
    content = _installed()
    assert 'nodl://test_ament_nodl/telemetry' in content
    assert 'local://' not in content


def test_share_copy_matches_the_index_copy():
    # Both install destinations get the rewritten document, so the two agree.
    assert _share_copy('composed_node.nodl.yaml') == _installed()


def test_rewrite_preserves_the_rest_of_the_document():
    content = _installed()
    assert 'Node composed from a local include' in content
    assert '/commands' in content


def test_consumer_resolves_the_rewritten_reference():
    # The point of rewriting: a consumer with no knowledge of the source layout resolves the chain.
    doc = load_nodl(_installed())
    assert any(p.name == '/telemetry/heartbeat' for p in doc.publishers)
    assert any(s.name == '/commands' for s in doc.subscriptions)
    assert doc.include is None


def test_referenced_document_is_registered_in_its_own_right():
    assert 'Shared telemetry surface' in _installed('telemetry')


def test_document_without_local_refs_is_installed_unchanged():
    # Only documents that actually have something to rewrite are re-serialized.
    assert _installed('basic_node') == _share_copy('basic_node.nodl.yaml')
