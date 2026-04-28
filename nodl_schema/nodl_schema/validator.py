"""Validate NoDL documents against the NoDL JSON Schema."""

from __future__ import annotations

import argparse
import sys
from importlib import resources
from pathlib import Path
from typing import Any, List

import yaml
from jsonschema import Draft202012Validator, RefResolver

_NODL_BASE_URI = "https://github.com/ros2/nodl/schemas/"


def _load_schema(name: str) -> dict:
    with resources.files("nodl_schema.schemas").joinpath(name).open("r") as f:
        return yaml.safe_load(f)


def _build_validator() -> Draft202012Validator:
    nodl_schema = _load_schema("nodl.schema.yaml")
    parameter_schema = _load_schema("parameter.schema.yaml")
    resolver = RefResolver(
        base_uri=_NODL_BASE_URI + "nodl.schema.yaml",
        referrer=nodl_schema,
        store={
            _NODL_BASE_URI + "nodl.schema.yaml": nodl_schema,
            _NODL_BASE_URI + "parameter.schema.yaml": parameter_schema,
        },
    )
    return Draft202012Validator(nodl_schema, resolver=resolver)


def _format_error(err) -> str:
    path = "/".join(str(p) for p in err.absolute_path) or "<root>"
    return f"{path}: {err.message}"


def validate(document: Any) -> List[str]:
    """Validate a parsed NoDL document. Return list of error messages (empty if valid)."""
    validator = _build_validator()
    return [_format_error(e) for e in sorted(validator.iter_errors(document), key=lambda e: list(e.absolute_path))]


def validate_file(path: Path) -> List[str]:
    """Validate a NoDL YAML file. Return list of error messages (empty if valid)."""
    with open(path, "r") as f:
        return validate(yaml.safe_load(f))


def main(argv: List[str] | None = None) -> int:
    """Entry point for the ``nodl-validate`` console script."""
    parser = argparse.ArgumentParser(description="Validate NoDL document(s) against the NoDL schema.")
    parser.add_argument("files", nargs="+", type=Path, help="NoDL YAML files to validate.")
    args = parser.parse_args(argv)

    rc = 0
    for path in args.files:
        errors = validate_file(path)
        if errors:
            rc = 1
            print(f"{path}: INVALID", file=sys.stderr)
            for e in errors:
                print(f"  {e}", file=sys.stderr)
        else:
            print(f"{path}: ok")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
