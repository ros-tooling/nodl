# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Validation and loading of ``codegen.python`` metadata."""

import importlib.resources as ir
import keyword
from typing import Optional

import yaml
from jsonschema import ValidationError
from jsonschema.validators import Draft7Validator

from nodl_generator_py.models import CodegenPython

CODEGEN_KEY = 'python'

_schema_cache: dict | None = None
_validator_cache: Draft7Validator | None = None


def load_schema() -> dict:
    """Load and cache the Python codegen JSON schema."""
    global _schema_cache
    if _schema_cache is None:
        path = ir.files('nodl_generator_py') / 'schemas' / 'codegen_python.schema.yaml'
        _schema_cache = yaml.safe_load(path.read_text(encoding='utf-8'))
    return _schema_cache


def _make_validator() -> Draft7Validator:
    global _validator_cache
    if _validator_cache is None:
        _validator_cache = Draft7Validator(load_schema())
    return _validator_cache


def validate(codegen: dict) -> None:
    """Validate this generator's metadata, if present."""
    python = codegen.get(CODEGEN_KEY)
    if python is not None:
        _make_validator().validate(python)
        names = [*python['module'].split('.'), python['class']]
        if 'publisher_method' in python:
            names.append(python['publisher_method'])
        invalid = next((name for name in names if keyword.iskeyword(name)), None)
        if invalid is not None:
            raise ValidationError(f'{invalid!r} is a Python keyword, not a valid codegen.python name')


def load(codegen: dict) -> Optional[CodegenPython]:
    """Validate and parse ``codegen.python``, or return ``None``."""
    python = codegen.get(CODEGEN_KEY)
    if python is None:
        return None
    validate(codegen)
    return CodegenPython.parse_obj(python)
