# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Compare every real observe MCAP fixture with its expected NoDL document."""

import json
import sys
from pathlib import Path

import pytest
import yaml

from nodl_schema import dump_nodl
from nodl_schema.validation import validate
from ros2nodl.describe import node_to_nodl

_FIXTURES = Path(__file__).parents[3] / 'nodl_observe' / 'test' / 'fixtures'
_GOLDENS = Path(__file__).parent / 'fixtures'


def test_golden_documents_are_valid_nodl():
    for golden in _GOLDENS.glob('*.nodl.yaml'):
        validate(yaml.safe_load(golden.read_text()))


@pytest.mark.parametrize('fixture', sorted(_FIXTURES.glob('*.mcap')), ids=lambda path: path.stem)
def test_observe_fixture_converts_to_valid_nodl(fixture):
    pytest.importorskip('rclpy')
    pytest.importorskip('mcap')
    pytest.importorskip('rosgraph_msgs')
    sys.path.insert(0, str(_FIXTURES.parent))
    import mcap_fixtures

    for channel, node in mcap_fixtures.read_fixture(str(fixture)).items():
        result = node_to_nodl(node)
        actual = json.loads(dump_nodl(result.doc, format='json'))
        profile = 'rmw_fastrtps_cpp' if 'rmw_fastrtps_cpp' in fixture.stem else 'base'
        golden = _GOLDENS / f'{profile}__{channel}.nodl.yaml'
        expected = yaml.safe_load(golden.read_text())

        validate(actual)
        assert result.gaps == []
        assert actual == expected
