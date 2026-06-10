# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""NoDL schema loading, validation, and serialization.

Two schemas are validated here:

* a NoDL **document** (``nodl.schema.yaml``) -- a possibly-partial node interface.
* a NoDL **node** (``node.schema.yaml``) -- a whole-node composition of
  ``base`` + ``mixins`` + ``main``, where each layer is a document.
"""

from __future__ import annotations

import importlib.resources as ir
import json
from pathlib import Path
from typing import IO, Union

import yaml
from jsonschema import RefResolver
from jsonschema.validators import Draft7Validator

from nodl_schema.composition import Node
from nodl_schema.models import NodlDocument

_document_validator: Draft7Validator | None = None
_node_validator: Draft7Validator | None = None
_schema_cache: dict | None = None


def _load_resource(name: str) -> dict:
    path = ir.files('nodl_schema') / 'schemas' / name
    return yaml.safe_load(path.read_text(encoding='utf-8'))


def load_schema() -> dict:
    """Load and cache the NoDL document JSON schema."""
    global _schema_cache
    if _schema_cache is None:
        _schema_cache = _load_resource('nodl.schema.yaml')
    return _schema_cache


def _resource_store() -> dict:
    """Build a $ref store so cross-file refs (node -> document -> parameter) resolve."""
    document = load_schema()
    parameter = _load_resource('parameter.schema.yaml')
    return {
        'nodl.schema.yaml': document,
        document.get('$id', ''): document,
        'parameter.schema.yaml': parameter,
        parameter.get('$id', ''): parameter,
    }


def _make_validator(schema: dict) -> Draft7Validator:
    store = _resource_store()
    resolver = RefResolver.from_schema(schema, store=store)
    return Draft7Validator(schema, resolver=resolver)


def validate(data: dict) -> None:
    """Validate a plain dict against the NoDL document schema.

    Raises jsonschema.ValidationError on failure.
    """
    global _document_validator
    if _document_validator is None:
        _document_validator = _make_validator(load_schema())
    _document_validator.validate(data)


def validate_node(data: dict) -> None:
    """Validate a plain dict against the NoDL node (composition) schema.

    Raises jsonschema.ValidationError on failure.
    """
    global _node_validator
    if _node_validator is None:
        _node_validator = _make_validator(_load_resource('node.schema.yaml'))
    _node_validator.validate(data)


def load_nodl(source: Union[str, bytes, IO]) -> NodlDocument:
    """Load and validate a NoDL document from a string, bytes, or file-like object.

    JSON is a subset of YAML, so both are accepted through yaml.safe_load.
    Raises jsonschema.ValidationError on schema error or pydantic.ValidationError
    on type error.
    """
    return NodlDocument.parse_obj(_load(source, validate))


def load_node(source: Union[str, bytes, IO]) -> Node:
    """Load and validate a NoDL node (composition) document.

    Same input handling as load_nodl, but validates and parses the
    base/main/mixins composition schema.
    """
    return Node.parse_obj(_load(source, validate_node))


def _load(source, validator) -> dict:
    data = yaml.safe_load(source)
    if not isinstance(data, dict):
        raise ValueError('NoDL document must be a YAML/JSON mapping at the top level')
    validator(data)
    return data


def _to_plain_dict(doc: Union[NodlDocument, Node]) -> dict:
    """Serialize a model to a JSON-compatible dict that drops Nones and unwraps enums.

    Goes via .json() so the result is a plain dict on both pydantic v1 and v2;
    v2's mode='json' equivalent is not available in v1.
    """
    return json.loads(doc.json(exclude_none=True))


def dump_nodl(doc: Union[NodlDocument, Node, dict], *, format: str = 'yaml') -> str:
    """Serialize a NodlDocument or Node (or plain dict) to a YAML or JSON string."""
    data = _to_plain_dict(doc) if not isinstance(doc, dict) else doc
    if format == 'json':
        return json.dumps(data, indent=2)
    return yaml.dump(data, default_flow_style=False, allow_unicode=True)


def main(argv: list[str] | None = None) -> int:
    """``python -m nodl_schema <file>`` -- validate a NoDL file.

    Exits 0 on success, 1 on validation failure or I/O error.
    Designed for invocation from CMake macros (ament_nodl_register_node and
    ament_nodl_register_document) so files are checked at build time, not at
    runtime.
    """
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        prog='python -m nodl_schema',
        description='Validate a NoDL file against the schema.',
    )
    parser.add_argument('file', type=Path, help='Path to the NoDL file to validate.')
    parser.add_argument(
        '--node',
        action='store_true',
        help='Validate the file as a NoDL node composition (base/main/mixins) rather than a document.',
    )
    args = parser.parse_args(argv)

    try:
        with args.file.open('r') as f:
            if args.node:
                load_node(f)
            else:
                load_nodl(f)
    except Exception as exc:
        print(f'{args.file}: {exc}', file=sys.stderr)
        return 1

    print(f'{args.file}: ok')
    return 0
