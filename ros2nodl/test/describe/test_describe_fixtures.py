# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Run the transform over every real observe MCAP fixture."""

import json
import sys
from pathlib import Path

import pytest

pytest.importorskip('rclpy')
pytest.importorskip('mcap')
pytest.importorskip('rosgraph_msgs')

from nodl_schema.validator import validate  # noqa: E402
from ros2nodl.describe import node_to_nodl  # noqa: E402

_FIXTURES = Path(__file__).parents[3] / 'nodl_observe' / 'test' / 'fixtures'
sys.path.insert(0, str(_FIXTURES.parent))

import mcap_fixtures  # noqa: E402


@pytest.mark.parametrize('fixture', sorted(_FIXTURES.glob('*.mcap')), ids=lambda path: path.stem)
def test_observe_fixture_converts_to_valid_nodl(fixture):
    for channel, node in mcap_fixtures.read_fixture(str(fixture)).items():
        result = node_to_nodl(node)
        data = json.loads(result.doc.json(exclude_none=True))
        validate(data)
        assert not [gap for gap in result.gaps if gap.path.endswith(('.name', '.type'))], (
            fixture.name,
            channel,
            result.gaps,
        )

        endpoints = [
            endpoint
            for key in (
                'publishers',
                'subscriptions',
                'service_servers',
                'service_clients',
                'action_servers',
                'action_clients',
            )
            for endpoint in data.get(key, [])
        ]
        assert all(endpoint.get('name') and endpoint.get('type') for endpoint in endpoints)
        names = {endpoint['name'] for endpoint in endpoints}
        assert '/rosout' not in names
        assert '/parameter_events' not in names
        assert not any('/_action/' in name for name in names)
        assert 'use_sim_time' not in data.get('parameters', {})
