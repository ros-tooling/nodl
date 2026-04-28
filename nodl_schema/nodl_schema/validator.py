"""Validate NoDL documents against the NoDL JSON Schema."""

from __future__ import annotations

from importlib import resources
from typing import Any, List

import yaml
from jsonschema import Draft202012Validator, RefResolver

_BASE_URI = "https://raw.githubusercontent.com/ros-tooling/nodl/main/nodl_schema/schemas/"
_NODL_SCHEMA_URI = _BASE_URI + "nodl.schema.yaml"
_PARAMETER_SCHEMA_URI = _BASE_URI + "parameter.schema.yaml"


def _load_schema(name: str) -> dict:
    with resources.files("nodl_schema.schemas").joinpath(name).open("r") as f:
        return yaml.safe_load(f)


def _build_validator() -> Draft202012Validator:
    nodl_schema = _load_schema("nodl.schema.yaml")
    parameter_schema = _load_schema("parameter.schema.yaml")
    resolver = RefResolver(
        base_uri=_NODL_SCHEMA_URI,
        referrer=nodl_schema,
        store={  # type: ignore[arg-type]
            _NODL_SCHEMA_URI: nodl_schema,
            _PARAMETER_SCHEMA_URI: parameter_schema,
        },
    )
    return Draft202012Validator(nodl_schema, resolver=resolver)


def _format_error(err) -> str:
    path = "/".join(str(p) for p in err.absolute_path) or "<root>"
    return f"{path}: {err.message}"


def validate(document: Any) -> List[str]:
    """Validate a parsed NoDL document. Return list of error messages (empty if valid)."""
    validator = _build_validator()
    return [
        _format_error(e)
        for e in sorted(validator.iter_errors(document), key=lambda e: list(e.absolute_path))
    ]
