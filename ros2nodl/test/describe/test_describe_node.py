# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0

import ros2nodl.describe as describe_api
from ros2nodl.describe import _source


def test_describe_node_acquires_and_converts(monkeypatch):
    observed = object()
    described = object()
    options = describe_api.DescribeOptions(include_parameters=False, keep_hidden=True)
    calls = {}

    def acquire_live(node_name, **kwargs):
        calls['acquire'] = (node_name, kwargs)
        return observed

    def node_to_nodl(node, opts):
        calls['convert'] = (node, opts)
        return described

    monkeypatch.setattr(_source, 'acquire_live', acquire_live)
    monkeypatch.setattr(describe_api, 'node_to_nodl', node_to_nodl)

    result = describe_api.describe_node('/robot/controller', timeout_sec=2.5, options=options)

    assert result is described
    assert calls['acquire'][0] == '/robot/controller'
    assert calls['acquire'][1]['timeout_sec'] == 2.5
    assert calls['acquire'][1]['include_parameters'] is False
    assert calls['acquire'][1]['topic'].startswith('/nodl/observed_node_')
    assert calls['convert'] == (observed, options)


def test_describe_node_uses_defaults_and_isolates_transport(monkeypatch):
    calls = []

    def acquire_live(node_name, **kwargs):
        calls.append((node_name, kwargs))
        return object()

    monkeypatch.setattr(_source, 'acquire_live', acquire_live)
    monkeypatch.setattr(describe_api, 'node_to_nodl', lambda node, opts: (node, opts))

    describe_api.describe_node('/first')
    describe_api.describe_node('/second')

    assert calls[0][1]['timeout_sec'] == 5.0
    assert calls[0][1]['include_parameters'] is True
    assert calls[0][1]['topic'] != calls[1][1]['topic']
