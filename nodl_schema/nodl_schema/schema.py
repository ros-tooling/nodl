# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Cached loading of JSON schema files and construction of validators from them."""

from __future__ import annotations

import functools
from pathlib import Path
from typing import Any

import yaml
from jsonschema import RefResolver, ValidationError
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


@functools.cache
def _variant_validators(schema: Path, tag: str) -> dict[str, Draft7Validator]:
    """Map each ``oneOf`` variant's *tag* ``const`` to a validator for that variant alone."""
    validator = schema_validator(schema)
    variants = {}
    for branch in load_schema_file(schema)['oneOf']:
        _, variant = validator.resolver.resolve(branch['$ref'])
        variants[variant['properties'][tag]['const']] = Draft7Validator(variant, resolver=validator.resolver)
    return variants


def validate_tagged(schema: Path, instance: Any, tag: str) -> None:
    """Validate *instance* against the variant of *schema* selected by its *tag* property.

    *schema* is a ``oneOf`` of ``$ref``s to object variants, each with a ``const`` *tag* property.
    Errors name the problem in the selected variant,
    rather than reporting that *instance* matches none of them.

    Raises :class:`jsonschema.ValidationError` on failure.
    """
    variants = _variant_validators(schema, tag)
    if not isinstance(instance, dict):
        raise ValidationError(f"{instance!r} is not of type 'object'")
    if tag not in instance:
        raise ValidationError(f'{tag!r} is a required property')
    value = instance[tag]
    if not isinstance(value, str) or value not in variants:
        raise ValidationError(f'{value!r} is not one of {list(variants)}')
    variants[value].validate(instance)
