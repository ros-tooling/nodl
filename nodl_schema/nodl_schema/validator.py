# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""NoDL schema loading, validation, and serialization.

Two schemas are validated here:

* an **interface definition** (``interface.schema.yaml``) -- a possibly-partial
  node interface.
* a **node definition** (``node.schema.yaml``) -- a whole-node composition of
  ``base`` + ``mixins`` + ``main``, where each layer is an interface definition.
"""

from __future__ import annotations

import importlib.resources as ir
import json
from pathlib import Path
from typing import IO, Union

import yaml
from jsonschema import RefResolver
from jsonschema.validators import Draft7Validator

from nodl_schema.models import Interface, Node

_interface_validator: Draft7Validator | None = None
_node_validator: Draft7Validator | None = None
_interface_schema_cache: dict | None = None


def _load_resource(name: str) -> dict:
    path = ir.files('nodl_schema') / 'schemas' / name
    return yaml.safe_load(path.read_text(encoding='utf-8'))


def load_interface_schema() -> dict:
    """Load and cache the NoDL interface definition JSON schema."""
    global _interface_schema_cache
    if _interface_schema_cache is None:
        _interface_schema_cache = _load_resource('interface.schema.yaml')
    return _interface_schema_cache


def _resource_store() -> dict:
    """Build a $ref store so cross-file refs (node -> interface -> parameter) resolve."""
    interface = load_interface_schema()
    parameter = _load_resource('parameter.schema.yaml')
    return {
        'interface.schema.yaml': interface,
        interface.get('$id', ''): interface,
        'parameter.schema.yaml': parameter,
        parameter.get('$id', ''): parameter,
    }


def _make_validator(schema: dict) -> Draft7Validator:
    store = _resource_store()
    resolver = RefResolver.from_schema(schema, store=store)
    return Draft7Validator(schema, resolver=resolver)


def validate_interface(data: dict) -> None:
    """Validate a plain dict against the NoDL interface definition schema.

    Raises jsonschema.ValidationError on failure.
    """
    global _interface_validator
    if _interface_validator is None:
        _interface_validator = _make_validator(load_interface_schema())
    _interface_validator.validate(data)


def validate_node(data: dict) -> None:
    """Validate a plain dict against the NoDL node definition (composition) schema.

    Raises jsonschema.ValidationError on failure.
    """
    global _node_validator
    if _node_validator is None:
        _node_validator = _make_validator(_load_resource('node.schema.yaml'))
    _node_validator.validate(data)


def load_interface(source: Union[str, bytes, IO]) -> Interface:
    """Load and validate a NoDL interface definition from a string, bytes, or file-like object.

    JSON is a subset of YAML, so both are accepted through yaml.safe_load.
    Raises jsonschema.ValidationError on schema error or pydantic.ValidationError
    on type error.
    """
    return Interface.parse_obj(_load(source, validate_interface))


def load_node(source: Union[str, bytes, IO]) -> Node:
    """Load and validate a NoDL node definition (composition).

    Same input handling as load_interface, but validates and parses the
    base/main/mixins composition schema.
    """
    return Node.parse_obj(_load(source, validate_node))


def _load(source, validator) -> dict:
    data = yaml.safe_load(source)
    if not isinstance(data, dict):
        raise ValueError('NoDL file must be a YAML/JSON mapping at the top level')
    validator(data)
    return data


def _to_plain_dict(doc: Union[Interface, Node]) -> dict:
    """Serialize a model to a JSON-compatible dict that drops Nones and unwraps enums.

    Goes via .json() so the result is a plain dict on both pydantic v1 and v2;
    v2's mode='json' equivalent is not available in v1.
    """
    return json.loads(doc.json(exclude_none=True))


def dump_nodl(doc: Union[Interface, Node, dict], *, format: str = 'yaml') -> str:
    """Serialize an Interface or Node (or plain dict) to a YAML or JSON string."""
    data = _to_plain_dict(doc) if not isinstance(doc, dict) else doc
    if format == 'json':
        return json.dumps(data, indent=2)
    return yaml.dump(data, default_flow_style=False, allow_unicode=True)


def main(argv: list[str] | None = None) -> int:
    """``python -m nodl_schema <file>`` -- validate a NoDL file.

    Exits 0 on success, 1 on validation failure or I/O error.
    Designed for invocation from CMake macros (ament_nodl_register_node and
    ament_nodl_register_interface) so files are checked at build time, not at
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
        help='Validate the file as a node definition (base/main/mixins) rather than an interface definition.',
    )
    args = parser.parse_args(argv)

    try:
        with args.file.open('r') as f:
            if args.node:
                load_node(f)
            else:
                load_interface(f)
    except Exception as exc:
        print(f'{args.file}: {exc}', file=sys.stderr)
        return 1

    print(f'{args.file}: ok')
    return 0
