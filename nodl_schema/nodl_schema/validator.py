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
    # parse_obj is pydantic v1 API, retained as a deprecated alias in v2.
    # Used so this module works against both rosdep-shipped pydantic v1
    # (humble/jazzy/kilted) and v2 (lyrical+).
    return NodlDocument.parse_obj(data)


def _to_plain_dict(doc: NodlDocument) -> dict:
    """Serialize a model to a JSON-compatible dict that drops Nones and unwraps enums.

    Goes via .json() so the result is a plain dict on both pydantic v1 and v2;
    v2's mode='json' equivalent is not available in v1.
    """
    return json.loads(doc.json(exclude_none=True))


def dump_nodl(doc: Union[NodlDocument, dict], *, format: str = 'yaml') -> str:
    """Serialize a NodlDocument (or plain dict) to YAML or JSON string."""
    data = _to_plain_dict(doc) if isinstance(doc, NodlDocument) else doc
    if format == 'json':
        return json.dumps(data, indent=2)
    return yaml.dump(data, default_flow_style=False, allow_unicode=True)
