# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Aliases are optional identifier fragments, separate from graph names."""

import pytest
from jsonschema import ValidationError

from nodl_schema import diff, dump_nodl, parse_nodl, validate
from nodl_schema.models import NodlDocument


@pytest.mark.parametrize(
    'kind', ['publishers', 'subscriptions', 'service_servers', 'service_clients', 'action_servers', 'action_clients']
)
@pytest.mark.parametrize('alias', ['x', 'good_name', 'mixedCase2', 'class'])
def test_alias_round_trip(kind, alias):
    endpoint = {'name': '/long/endpoint', 'type': 'example_interfaces/Fibonacci', 'alias': alias}
    if kind in ('publishers', 'subscriptions'):
        endpoint['qos'] = {'history': 'SYSTEM_DEFAULT', 'reliability': 'SYSTEM_DEFAULT'}
    data = {'nodl_version': 2, kind: [endpoint]}
    validate(data)
    doc = NodlDocument.parse_obj(data)
    assert getattr(parse_nodl(dump_nodl(doc)), kind)[0].alias == alias
    endpoint.pop('alias')
    assert diff(doc, NodlDocument.parse_obj(data), node_fqn='/test') == []


@pytest.mark.parametrize('alias', ['', 'Upper', '_private', '1st', 'a-b', 'a/b', 'a b', None, 123])
def test_invalid_alias(alias):
    with pytest.raises(ValidationError):
        validate({
            'nodl_version': 2,
            'service_clients': [{'name': '/real', 'type': 'std_srvs/Trigger', 'alias': alias}],
        })
