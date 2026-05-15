"""NoDL schema loading, validation, and serialization."""

from __future__ import annotations

import importlib.resources as ir
import json
from typing import IO, Union

import yaml
from jsonschema.validators import Draft202012Validator

from nodl.models import NodlDocument

_schema_cache: dict | None = None
_validator_cache: Draft202012Validator | None = None


def _load_resource(name: str) -> dict:
    path = ir.files('nodl') / 'resources' / name
    return yaml.safe_load(path.read_text(encoding='utf-8'))


def load_schema() -> dict:
    """Load and cache the NoDL JSON schema."""
    global _schema_cache
    if _schema_cache is None:
        _schema_cache = _load_resource('nodl.schema.yaml')
    return _schema_cache


def _make_validator() -> Draft202012Validator:
    """Build a validator with the parameter schema pre-loaded in the store."""
    global _validator_cache
    if _validator_cache is None:
        schema = load_schema()
        param_schema = _load_resource('parameter.schema.yaml')
        store = {param_schema['$id']: param_schema}
        _validator_cache = Draft202012Validator(
            schema,
            resolver=Draft202012Validator.VALIDATORS and None,
        )
        # Build with a custom registry/store for older jsonschema API
        from jsonschema import RefResolver
        resolver = RefResolver.from_schema(schema, store=store)
        _validator_cache = Draft202012Validator(schema, resolver=resolver)
    return _validator_cache


def validate(data: dict) -> None:
    """Validate a plain dict against the NoDL JSON schema.

    Raises jsonschema.ValidationError on failure.
    """
    _make_validator().validate(data)


def load_nodl(source: Union[str, bytes, IO], *, format: str | None = None) -> NodlDocument:
    """Load and validate a NoDL document from a string, bytes, or file-like object.

    format: 'yaml', 'json', or None (auto-detect from content).
    Returns a validated NodlDocument. Raises ValueError on parse error,
    ValidationError on schema error, or ValidationError from pydantic on type error.
    """
    if hasattr(source, 'read'):
        content = source.read()
    elif isinstance(source, (str, bytes)):
        content = source
    else:
        raise TypeError(f'Expected str, bytes, or file-like object, got {type(source)}')

    if isinstance(content, bytes):
        content = content.decode('utf-8')

    if format == 'json':
        data = json.loads(content)
    elif format == 'yaml':
        data = yaml.safe_load(content)
    else:
        # Auto-detect: try JSON first (strict), fall back to YAML
        stripped = content.lstrip()
        if stripped.startswith('{') or stripped.startswith('['):
            data = json.loads(content)
        else:
            data = yaml.safe_load(content)

    if not isinstance(data, dict):
        raise ValueError('NoDL document must be a YAML/JSON mapping at the top level')

    validate(data)
    return NodlDocument.model_validate(data)


def dump_nodl(doc: Union[NodlDocument, dict], *, format: str = 'yaml') -> str:
    """Serialize a NodlDocument (or plain dict) to YAML or JSON string."""
    data = doc.to_dict() if isinstance(doc, NodlDocument) else doc
    if format == 'json':
        return json.dumps(data, indent=2)
    return yaml.dump(data, default_flow_style=False, allow_unicode=True)
