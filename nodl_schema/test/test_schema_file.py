# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for cached schema file loading and validator construction."""

import pytest
import yaml
from jsonschema import ValidationError

from nodl_schema.schema import load_schema_file, schema_validator, validate_tagged


def _write(path, schema):
    path.write_text(yaml.safe_dump(schema), encoding='utf-8')
    return path


@pytest.fixture
def referenced(tmp_path):
    return _write(tmp_path / 'positive.schema.yaml', {'$id': 'urn:test:positive', 'type': 'integer', 'minimum': 1})


def test_load_schema_file_cached(referenced):
    assert load_schema_file(referenced) is load_schema_file(referenced)


def test_schema_validator_cached(referenced):
    assert schema_validator(referenced) is schema_validator(referenced)


@pytest.mark.parametrize('ref', ['positive.schema.yaml', 'urn:test:positive'])
def test_schema_validator_resolves_references_by_name_and_id(tmp_path, referenced, ref):
    root = _write(tmp_path / f'root_{abs(hash(ref))}.schema.yaml', {'properties': {'count': {'$ref': ref}}})
    validator = schema_validator(root, referenced)

    validator.validate({'count': 1})
    with pytest.raises(ValidationError):
        validator.validate({'count': 0})


@pytest.fixture
def tagged(tmp_path):
    return _write(
        tmp_path / 'tagged.schema.yaml',
        {
            'oneOf': [{'$ref': '#/definitions/a'}, {'$ref': '#/definitions/b'}],
            'definitions': {
                'a': {
                    'type': 'object',
                    'additionalProperties': False,
                    'required': ['kind', 'size'],
                    'properties': {'kind': {'const': 'A'}, 'size': {'type': 'integer'}},
                },
                'b': {
                    'type': 'object',
                    'additionalProperties': False,
                    'required': ['kind'],
                    'properties': {'kind': {'const': 'B'}},
                },
            },
        },
    )


@pytest.mark.parametrize('instance', [{'kind': 'A', 'size': 1}, {'kind': 'B'}])
def test_validate_tagged_accepts_each_variant(tagged, instance):
    validate_tagged(tagged, instance, 'kind')


@pytest.mark.parametrize(
    'instance,message',
    [
        ({'kind': 'A'}, "'size' is a required property"),
        ({'kind': 'B', 'size': 1}, "'size' was unexpected"),
        ({'kind': 'C'}, r"'C' is not one of \['A', 'B'\]"),
        ({'kind': ['A']}, r"\['A'\] is not one of"),
        ({}, "'kind' is a required property"),
        ('A', "is not of type 'object'"),
    ],
)
def test_validate_tagged_reports_the_selected_variant_error(tagged, instance, message):
    with pytest.raises(ValidationError, match=message):
        validate_tagged(tagged, instance, 'kind')
