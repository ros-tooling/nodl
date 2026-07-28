# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""NoDL schema loading, validation, and serialization."""

from __future__ import annotations

import importlib.resources as ir
import json
from pathlib import Path
from typing import IO, Union

import yaml
from jsonschema import RefResolver
from jsonschema.validators import Draft7Validator

from nodl_schema.models import NodlDocument

_schema_cache: dict | None = None
_validator_cache: Draft7Validator | None = None


def _load_resource(name: str) -> dict:
    path = ir.files('nodl_schema') / 'schemas' / name
    return yaml.safe_load(path.read_text(encoding='utf-8'))


def load_schema() -> dict:
    """Load and cache the NoDL JSON schema."""
    global _schema_cache
    if _schema_cache is None:
        _schema_cache = _load_resource('nodl.schema.yaml')
    return _schema_cache


def _make_validator() -> Draft7Validator:
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
        _validator_cache = Draft7Validator(schema, resolver=resolver)
    return _validator_cache


def validate(data: dict) -> None:
    """Validate a plain dict against the NoDL JSON schema.

    Raises jsonschema.ValidationError on failure.
    """
    _make_validator().validate(data)


def load_nodl(source: Union[str, bytes, IO], *, resolve: bool = True, resolver=None) -> NodlDocument:
    """Load and validate a NoDL document from a string, bytes, or file-like object.

    JSON is a subset of YAML, so both are accepted through yaml.safe_load.

    When ``resolve`` is true (the default) and the document has an ``include``
    list, each reference is resolved and its entities are merged in (see
    nodl_schema.composition); the returned document carries the merged
    interface and no ``include`` key. ``resolver`` overrides the default
    ament/http resolver, mainly for tests. Pass ``resolve=False`` to parse the
    document as authored, leaving ``include`` intact and following nothing.

    Raises jsonschema.ValidationError on schema error, pydantic.ValidationError
    on type error, or composition.CompositionError on an unresolvable or
    conflicting include.
    """
    data = yaml.safe_load(source)
    if not isinstance(data, dict):
        raise ValueError('NoDL document must be a YAML/JSON mapping at the top level')

    validate(data)

    if resolve and data.get('include'):
        # Imported lazily to avoid a circular import (composition validates included docs via this module).
        from nodl_schema.composition import resolve_document

        data = resolve_document(data, resolver)
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


def main(argv: list[str] | None = None) -> int:
    """``python -m nodl_schema <file>`` -- validate a NoDL file.

    Exits 0 on success, 1 on validation failure or I/O error.
    Designed for invocation from CMake macros (ament_nodl_register_node and
    siblings) so files are checked at build time, not at runtime.
    """
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        prog='python -m nodl_schema',
        description='Validate a NoDL file against the schema.',
    )
    parser.add_argument('file', type=Path, help='Path to the NoDL file to validate.')
    parser.add_argument(
        '--no-resolve',
        dest='resolve',
        action='store_false',
        help='Validate the schema only; do not resolve include references. '
        'By default includes are resolved so the file is checked for resolvability too.',
    )
    args = parser.parse_args(argv)

    try:
        with args.file.open('r') as f:
            load_nodl(f, resolve=args.resolve)
    except Exception as exc:
        print(f'{args.file}: {exc}', file=sys.stderr)
        return 1

    print(f'{args.file}: ok')
    return 0
