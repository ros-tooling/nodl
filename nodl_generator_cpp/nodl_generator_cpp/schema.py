# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Validation and loading of the ``codegen.cpp`` metadata from NoDL documents."""

from __future__ import annotations

import importlib.resources as ir
from typing import Optional

import yaml
from jsonschema.validators import Draft7Validator

from nodl_generator_cpp.models import CodegenCpp

# The key within the top-level ``codegen`` dict that this package owns.
CODEGEN_KEY = 'cpp'

_schema_cache: dict | None = None
_validator_cache: Draft7Validator | None = None


def load_schema() -> dict:
    """Load and cache the codegen_cpp JSON schema."""
    global _schema_cache
    if _schema_cache is None:
        path = ir.files('nodl_generator_cpp') / 'schemas' / 'codegen_cpp.schema.yaml'
        _schema_cache = yaml.safe_load(path.read_text(encoding='utf-8'))
    return _schema_cache


def _make_validator() -> Draft7Validator:
    """Build and cache a Draft7Validator for the codegen_cpp schema."""
    global _validator_cache
    if _validator_cache is None:
        _validator_cache = Draft7Validator(load_schema())
    return _validator_cache


def validate(codegen: dict) -> None:
    """Validate the ``codegen`` dict from a NoDL document.

    Extracts the ``cpp`` sub-object (keyed by :data:`CODEGEN_KEY`) and
    validates it against ``codegen_cpp.schema.yaml``.

    Does nothing if ``codegen`` has no ``cpp`` key.

    Raises :class:`jsonschema.ValidationError` on schema violation.
    """
    cpp = codegen.get(CODEGEN_KEY)
    if cpp is None:
        return
    _make_validator().validate(cpp)


def load(codegen: dict) -> Optional[CodegenCpp]:
    """Validate and load the ``codegen.cpp`` metadata as a :class:`CodegenCpp` model.

    Returns ``None`` if ``codegen`` has no ``cpp`` key (keyed by :data:`CODEGEN_KEY`).

    Raises :class:`jsonschema.ValidationError` on schema violation.
    Raises :class:`pydantic.ValidationError` on type error.
    """
    cpp = codegen.get(CODEGEN_KEY)
    if cpp is None:
        return None
    validate(codegen)
    return CodegenCpp.parse_obj(cpp)
