# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Cached loading of JSON schema files and construction of validators from them."""

from __future__ import annotations

import functools
from pathlib import Path

import yaml
from jsonschema import RefResolver
from jsonschema.validators import Draft7Validator


@functools.cache
def load_schema_file(path: Path) -> dict:
    """Load and cache a JSON schema from a YAML or JSON file."""
    return yaml.safe_load(path.read_text(encoding='utf-8'))


@functools.cache
def schema_validator(schema: Path, *references: Path) -> Draft7Validator:
    """Build and cache a validator for the schema at *schema*.

    Each of *references* is a schema that *schema* refers to with ``$ref``,
    resolvable by its file name and by its ``$id``.
    """
    store = {}
    for reference in references:
        referenced = load_schema_file(reference)
        store[reference.name] = referenced
        if '$id' in referenced:
            store[referenced['$id']] = referenced
    root = load_schema_file(schema)
    # TODO(emerson) RefResolver is deprecated in favor of https://github.com/python-jsonschema/referencing
    return Draft7Validator(root, resolver=RefResolver.from_schema(root, store=store))
