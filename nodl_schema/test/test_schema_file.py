# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for cached schema file loading and validator construction."""

import pytest
import yaml
from jsonschema import ValidationError

from nodl_schema.schema import load_schema_file, schema_validator


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
