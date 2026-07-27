# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""NoDL schema loading, validation, and serialization."""

from __future__ import annotations

import importlib.resources as ir
import json
from pathlib import Path

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


# ---------------------------------------------------------------------------
# Include-resolution helpers
# ---------------------------------------------------------------------------

# Endpoint sections that use list-of-objects keyed by ``name``.
_LIST_SECTIONS = (
    'publishers',
    'subscriptions',
    'service_servers',
    'service_clients',
    'action_servers',
    'action_clients',
)


def _resolve_ref(ref: str, base_dir: Path) -> Path:
    """Resolve a single include *ref* to an absolute file path.

    Currently handles relative paths (``./…`` / ``../…``).  Package URIs
    (``nodl://…``) are handled in Phase 3.
    """
    if ref.startswith('./') or ref.startswith('../'):
        resolved = (base_dir / ref).resolve()
        if not resolved.is_file():
            raise FileNotFoundError(f'Include ref {ref!r} resolved to {resolved} which does not exist')
        return resolved
    raise ValueError(f'Unsupported include ref {ref!r} — package URIs (nodl://…) are not yet implemented')


def _endpoints_equal(a: dict, b: dict) -> bool:
    """Return True when two plain-dict endpoints are semantically identical."""
    return a == b


def _merge_list_section(
    local: list[dict] | None,
    included: list[dict] | None,
    section: str,
    source_label: str,
) -> list[dict] | None:
    """Merge a list-of-endpoint section (*publishers*, *subscriptions*, …).

    Local declarations win.  Among included entries, identical duplicates
    are silently deduplicated; conflicting duplicates (same ``name``,
    different definition) raise ``ValueError``.
    """
    if not included:
        return local

    local_by_name: dict[str, dict] = {}
    if local:
        for ep in local:
            local_by_name[ep['name']] = ep

    merged_by_name: dict[str, dict] = dict(local_by_name)

    for ep in included:
        name = ep['name']
        if name in local_by_name:
            # Local wins — skip the included version.
            continue
        if name in merged_by_name:
            if _endpoints_equal(merged_by_name[name], ep):
                continue  # identical duplicate from another include
            raise ValueError(
                f"Merge conflict in {section}: '{name}' is defined differently in multiple includes ({source_label})"
            )
        merged_by_name[name] = ep

    return list(merged_by_name.values()) if merged_by_name else None


def _merge_parameters(
    local: dict[str, dict] | None,
    included: dict[str, dict] | None,
    source_label: str,
) -> dict[str, dict] | None:
    """Merge parameter dicts.  Same rules as list sections."""
    if not included:
        return local

    local = local or {}
    merged = dict(local)

    for name, defn in included.items():
        if name in local:
            continue  # local wins
        if name in merged:
            if merged[name] == defn:
                continue
            raise ValueError(
                f"Merge conflict in parameters: '{name}' is defined differently in multiple includes ({source_label})"
            )
        merged[name] = defn

    return merged if merged else None


def _load_and_resolve(
    data: dict,
    base_dir: Path,
    seen: set[Path],
) -> dict:
    """Recursively resolve includes in *data* and return a merged plain dict.

    *base_dir* is the directory containing the file that produced *data*.
    *seen* tracks canonical paths already visited (diamond / cycle guard).
    """
    includes = data.get('includes')
    if not includes:
        # Nothing to resolve — strip includes key and return.
        result = {k: v for k, v in data.items() if k != 'includes'}
        return result

    # Accumulate all included (already-merged) interface data.
    all_included_params: dict[str, dict] = {}
    all_included_lists: dict[str, list[dict]] = {s: [] for s in _LIST_SECTIONS}

    for inc in includes:
        ref = inc['ref']
        resolved = _resolve_ref(ref, base_dir)
        canonical = resolved.resolve()
        if canonical in seen:
            continue  # already processed (diamond / cycle)
        seen.add(canonical)

        child_text = resolved.read_text(encoding='utf-8')
        child_data = yaml.safe_load(child_text)
        validate(child_data)

        # Recurse into the child.
        child_merged = _load_and_resolve(
            child_data,
            base_dir=resolved.parent,
            seen=seen,
        )

        # Collect child interfaces into the accumulated pools.
        child_params = child_merged.get('parameters')
        if child_params:
            all_included_params = _merge_parameters(all_included_params, child_params, source_label=str(resolved)) or {}

        for section in _LIST_SECTIONS:
            child_list = child_merged.get(section)
            if child_list:
                all_included_lists[section].extend(child_list)

    # Build result: start from local data (without includes).
    result = {k: v for k, v in data.items() if k != 'includes'}

    # Merge parameters.
    merged_params = _merge_parameters(result.get('parameters'), all_included_params, source_label='includes')
    if merged_params:
        result['parameters'] = merged_params

    # Merge list sections.
    for section in _LIST_SECTIONS:
        included_list = all_included_lists[section]
        merged = _merge_list_section(result.get(section), included_list or None, section, source_label='includes')
        if merged:
            result[section] = merged

    return result


def load_nodl(source: Path) -> NodlDocument:
    """Load, validate, and resolve includes in a NoDL file.

    Reads the file at *source*, validates it against the NoDL schema,
    recursively resolves any ``includes`` (relative paths resolved
    against the file's parent directory), and returns a merged
    ``NodlDocument`` with the ``includes`` field stripped.

    Raises ``jsonschema.ValidationError`` on schema error or
    ``pydantic.ValidationError`` on type error.
    """
    data = yaml.safe_load(source.read_text(encoding='utf-8'))

    if not isinstance(data, dict):
        raise ValueError('NoDL document must be a YAML/JSON mapping at the top level')

    validate(data)

    # Resolve includes if present.
    if data.get('includes'):
        seen: set[Path] = {source.resolve()}
        data = _load_and_resolve(data, base_dir=source.parent, seen=seen)

    # Strip includes from the final data before model construction.
    data.pop('includes', None)

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


def dump_nodl(doc: NodlDocument | dict, *, format: str = 'yaml') -> str:
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
    args = parser.parse_args(argv)

    try:
        data = yaml.safe_load(args.file.read_text(encoding='utf-8'))
        if not isinstance(data, dict):
            raise ValueError('NoDL document must be a YAML/JSON mapping at the top level')
        validate(data)
    except Exception as exc:
        print(f'{args.file}: {exc}', file=sys.stderr)
        return 1

    print(f'{args.file}: ok')
    return 0
