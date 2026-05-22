# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""NoDL schema loading, validation, and serialization."""

from __future__ import annotations

import importlib.resources as ir
import json
from typing import IO, Union

import yaml
from jsonschema import RefResolver
from jsonschema.validators import Draft202012Validator

from nodl_schema.models import NodlDocument

_schema_cache: dict | None = None
_validator_cache: Draft202012Validator | None = None


def _load_resource(name: str) -> dict:
    path = ir.files('nodl_schema') / 'schemas' / name
    return yaml.safe_load(path.read_text(encoding='utf-8'))


def load_schema() -> dict:
    """Load and cache the NoDL JSON schema."""
    global _schema_cache
    if _schema_cache is None:
        _schema_cache = _load_resource('nodl.schema.yaml')
    return _schema_cache


def _make_validator() -> Draft202012Validator:
    """Build a validator with the parameter schema pre-loaded so $refs resolve."""
    global _validator_cache
    if _validator_cache is None:
        schema = load_schema()
        param_schema = _load_resource('parameter.schema.yaml')
        store = {
            'parameter.schema.yaml': param_schema,
            param_schema.get('$id', ''): param_schema,
        }
        resolver = RefResolver.from_schema(schema, store=store)
        _validator_cache = Draft202012Validator(schema, resolver=resolver)
    return _validator_cache


def validate(data: dict) -> None:
    """Validate a plain dict against the NoDL JSON schema.

    Raises jsonschema.ValidationError on failure.
    """
    _make_validator().validate(data)


def load_nodl(source: Union[str, bytes, IO]) -> NodlDocument:
    """Load and validate a NoDL document from a string, bytes, or file-like object.

    JSON is a subset of YAML, so both are accepted through yaml.safe_load.
    Raises jsonschema.ValidationError on schema error or pydantic.ValidationError
    on type error.
    """
    data = yaml.safe_load(source)
    if not isinstance(data, dict):
        raise ValueError('NoDL document must be a YAML/JSON mapping at the top level')

    validate(data)
    return NodlDocument.model_validate(data)


def dump_nodl(doc: Union[NodlDocument, dict], *, format: str = 'yaml') -> str:
    """Serialize a NodlDocument (or plain dict) to YAML or JSON string."""
    if isinstance(doc, NodlDocument):
        data = doc.model_dump(exclude_none=True, mode='json')
    else:
        data = doc
    if format == 'json':
        return json.dumps(data, indent=2)
    return yaml.dump(data, default_flow_style=False, allow_unicode=True)
