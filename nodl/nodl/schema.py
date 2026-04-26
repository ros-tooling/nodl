"""NoDL schema loading, validation, and serialization."""

from __future__ import annotations

import importlib.resources as ir
import json
from typing import IO, Union

import yaml
from jsonschema.validators import Draft202012Validator

from nodl.models import NodlDocument

_schema_cache: dict | None = None


def load_schema() -> dict:
    """Load and cache the NoDL JSON schema."""
    global _schema_cache
    if _schema_cache is None:
        schema_path = ir.files('nodl') / 'resources' / 'nodl.schema.yaml'
        _schema_cache = yaml.safe_load(schema_path.read_text(encoding='utf-8'))
    return _schema_cache


def validate(data: dict) -> None:
    """Validate a plain dict against the NoDL JSON schema.

    Raises jsonschema.ValidationError on failure.
    """
    schema = load_schema()
    Draft202012Validator(schema).validate(data)


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
