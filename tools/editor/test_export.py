# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Ensure published schemas are faithful, current exports of the canonical YAML."""

import json
from pathlib import Path

from export_schemas import export_schemas
from jsonschema import Draft7Validator

ROOT = Path(__file__).resolve().parents[2]
SCHEMAS = ROOT / 'nodl_schema/nodl_schema/schemas'


def test_published_schemas_are_current(tmp_path):
    export_schemas(sorted(SCHEMAS.glob('*.yaml')), tmp_path)
    for generated in tmp_path.glob('*.json'):
        published = SCHEMAS / generated.name
        assert json.loads(published.read_text()) == json.loads(generated.read_text()), f'Regenerate {published}'
        Draft7Validator.check_schema(json.loads(published.read_text()))


def test_export_preserves_fragments_and_unrelated_references(tmp_path):
    source = tmp_path / 'sample.yaml'
    source.write_text(
        '$id: sample.yaml\n'
        'allOf:\n'
        '  - $ref: sample.yaml#/definitions/value\n'
        '  - $ref: "#/definitions/value"\n'
        '  - $ref: https://example.com/external.yaml\n'
        'description: sample.yaml\n'
    )
    output = tmp_path / 'output'
    export_schemas([source], output)
    assert json.loads((output / 'sample.json').read_text()) == {
        '$id': 'sample.json',
        'allOf': [
            {'$ref': 'sample.json#/definitions/value'},
            {'$ref': '#/definitions/value'},
            {'$ref': 'https://example.com/external.yaml'},
        ],
        'description': 'sample.yaml',
    }
