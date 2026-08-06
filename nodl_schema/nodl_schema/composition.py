# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Composition of NoDL documents via the ``include`` key.

A document may list other NoDL documents under ``include``; each reference is
resolved, validated, and its interface entities (parameters, publishers,
subscriptions, service/action servers and clients) are merged into the
including document. Includes are followed recursively, and a name collision
within any single category is an error.

Two reference forms are accepted:

* ``nodl://<package>/<name>`` -- a registered document in an already-installed
  package, looked up in the ament index as the resource
  ``nodl_nodes/<package>__<name>`` that ``ament_nodl_register_node`` installs.
* a relative path -- a document in the same package, resolved against the
  directory of the document holding the reference. This is the only form that
  can reach a document in the package currently being built, since it reads the
  source tree rather than an installed workspace.

A reference is normalized against its document's *origin* before it is fetched,
so a relative path becomes an absolute ``file://`` reference and the ``Resolver``
protocol stays a plain ``ref -> text`` function. Adding a reference form later is
therefore a matter of teaching a resolver a new scheme: nothing downstream of the
fetch inspects the reference that produced the text.

Relative references are an intra-package authoring convenience and do not survive
installation. ``ament_nodl_register_node`` rewrites them to their ``nodl://``
equivalents before installing, using :func:`local_references` to find them and
:func:`rewrite_references` to replace them.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Protocol, runtime_checkable

import yaml

# Entity categories merged as name-keyed lists. Parameters are handled separately (a dict).
_ENTITY_LIST_KEYS = (
    'publishers',
    'subscriptions',
    'service_servers',
    'service_clients',
    'action_servers',
    'action_clients',
)

_NODL_SCHEME = 'nodl://'
_FILE_SCHEME = 'file://'
# Resource type under which ament_nodl_register_node publishes a document; the key is <package>__<name>.
_AMENT_RESOURCE_TYPE = 'nodl_nodes'


class CompositionError(Exception):
    """Raised when includes cannot be resolved or merged (unresolvable ref, cycle, or name collision)."""


@runtime_checkable
class Resolver(Protocol):
    """Turns a reference string into the raw text of the referenced NoDL document."""

    def fetch(self, ref: str) -> str: ...


class DefaultResolver:
    """Resolves ``nodl://`` references through the ament index and ``file://`` references from disk."""

    def fetch(self, ref: str) -> str:
        if ref.startswith(_NODL_SCHEME):
            return self._fetch_ament(ref)
        if ref.startswith(_FILE_SCHEME):
            return self._fetch_file(ref)
        raise CompositionError(
            f'unsupported reference scheme: {ref!r} '
            f'(expected {_NODL_SCHEME}, or a relative path resolved to {_FILE_SCHEME})'
        )

    def _fetch_ament(self, ref: str) -> str:
        package, _, name = ref[len(_NODL_SCHEME) :].partition('/')
        if not package or not name:
            raise CompositionError(f'invalid nodl:// reference {ref!r}: expected nodl://<package>/<name>')
        # Imported lazily and called by attribute so environments without a ROS install can still
        # use an injected resolver, and so tests can monkeypatch the lookup.
        try:
            from ament_index_python import resources
        except ImportError as exc:
            raise CompositionError(f'ament_index_python is required to resolve {ref!r}') from exc
        key = f'{package}__{name}'
        try:
            content, _ = resources.get_resource(_AMENT_RESOURCE_TYPE, key)
        except Exception as exc:
            raise CompositionError(
                f'NoDL document not found in ament index for {ref!r} '
                f'(looked up as {_AMENT_RESOURCE_TYPE}/{key}); '
                f'is the providing package built and a dependency of this one?'
            ) from exc
        return content

    def _fetch_file(self, ref: str) -> str:
        path = ref_to_path(ref)
        try:
            return path.read_text(encoding='utf-8')
        except OSError as exc:
            raise CompositionError(f'could not read {str(path)!r}: {exc}') from exc


def is_relative_ref(ref: str) -> bool:
    """True when ``ref`` is a relative path rather than an absolute, scheme-qualified reference."""
    return not ref.startswith(_NODL_SCHEME) and not ref.startswith(_FILE_SCHEME)


def path_to_ref(path: Path | str) -> str:
    """Turn a filesystem path into an absolute ``file://`` reference."""
    return _FILE_SCHEME + str(Path(path).resolve())


def ref_to_path(ref: str) -> Path:
    """Turn a ``file://`` reference back into a filesystem path."""
    return Path(ref[len(_FILE_SCHEME) :])


def _normalize(ref: str, origin: str | None) -> str:
    """Resolve ``ref`` against ``origin`` so it is absolute and scheme-qualified.

    ``nodl://`` references pass through. A relative path is resolved against the directory of
    ``origin``, which must itself be a ``file://`` reference: a document fetched from the ament
    index is text with no location, so nothing inside it can be relative to anything.
    """
    if not is_relative_ref(ref):
        return ref
    if origin is None:
        raise CompositionError(
            f'relative reference {ref!r} has nothing to resolve against; '
            f'load the document from a file, or pass base= to load_nodl'
        )
    if not origin.startswith(_FILE_SCHEME):
        raise CompositionError(
            f'relative reference {ref!r} appears in {origin!r}, which was not loaded from a file; '
            f'a document resolved through the ament index has no location to be relative to'
        )
    return path_to_ref(ref_to_path(origin).parent / ref)


def resolve_document(
    data: dict,
    resolver: Resolver | None = None,
    *,
    origin: str | None = None,
    _stack: list[str] | None = None,
) -> dict:
    """Return a copy of ``data`` with its ``include`` list resolved and merged in.

    Each reference is normalized against ``origin`` (the reference the document itself was
    fetched from, if any), fetched via ``resolver`` (``DefaultResolver`` if none is given),
    schema-validated, recursively resolved, and merged. The returned dict has no ``include``
    key. The input ``data`` is not mutated.

    Raises ``CompositionError`` on an unresolvable reference, an include cycle, or a name
    collision within a category; raises ``jsonschema.ValidationError`` if an included
    document does not satisfy the schema.
    """
    if resolver is None:
        resolver = DefaultResolver()
    stack = _stack or []

    result = copy.deepcopy(data)
    includes = result.pop('include', None) or []

    for entry in includes:
        authored = entry['ref']
        # Normalizing before the cycle check means two spellings of the same file are recognized
        # as one document rather than recursing until something else gives way.
        ref = _normalize(authored, origin)
        if ref in stack:
            chain = ' -> '.join([*stack, ref])
            raise CompositionError(f'include cycle detected: {chain}')

        text = _fetch(resolver, ref)
        child = yaml.safe_load(text)
        if not isinstance(child, dict):
            raise CompositionError(f'included document {ref!r} is not a YAML/JSON mapping')

        _validate(child, ref)
        resolved_child = resolve_document(child, resolver, origin=ref, _stack=[*stack, ref])
        _merge_into(result, resolved_child, ref)

    return result


def local_references(data: dict, origin: str, *, _seen: list[Path] | None = None) -> list[Path]:
    """Return every document reachable from ``data`` through relative references, transitively.

    ``origin`` is the ``file://`` reference ``data`` was read from. The result is a list of
    absolute paths in discovery order, deduplicated, and safe against reference cycles.

    ``ament_nodl_register_node`` uses this at configure time for two things: to check that each
    referenced document has already been registered, and to feed CMake the dependency list so
    editing a document two levels down still reruns validation.
    """
    seen = [] if _seen is None else _seen

    for entry in data.get('include') or []:
        ref = entry.get('ref')
        if not ref or not is_relative_ref(ref):
            continue
        child_ref = _normalize(ref, origin)
        path = ref_to_path(child_ref)
        if path in seen:
            continue
        seen.append(path)

        try:
            child = yaml.safe_load(path.read_text(encoding='utf-8'))
        except OSError as exc:
            raise CompositionError(f'could not read {ref!r} from {str(path)!r}: {exc}') from exc
        if isinstance(child, dict):
            local_references(child, child_ref, _seen=seen)

    return seen


def rewrite_references(data: dict, mapping: dict[Path, str], origin: str) -> dict:
    """Return a copy of ``data`` with each relative reference replaced by its ``nodl://`` form.

    ``mapping`` maps an absolute path to the ``<package>/<name>`` it was registered as.
    ``nodl://`` references are left alone, and nothing is merged: this rewrites the reference
    and changes nothing else, so the result differs from the authored document only in the
    spelling of its references.

    Rewriting is not recursive. Every registered document is rewritten by its own registration,
    so a document that includes a document that includes a third one needs no special handling
    here.
    """
    result = copy.deepcopy(data)

    for entry in result.get('include') or []:
        ref = entry.get('ref')
        if not ref or not is_relative_ref(ref):
            continue
        path = ref_to_path(_normalize(ref, origin))
        target = mapping.get(path)
        if target is None:
            raise CompositionError(
                f'{ref!r} resolves to {str(path)!r}, which is not registered; '
                f'register it with ament_nodl_register_node before the document that includes it'
            )
        entry['ref'] = _NODL_SCHEME + target

    return result


def _fetch(resolver: Resolver, ref: str) -> str:
    """Fetch through an injected resolver, normalizing its failures to CompositionError."""
    try:
        return resolver.fetch(ref)
    except CompositionError:
        raise
    except Exception as exc:
        raise CompositionError(f'could not resolve include {ref!r}: {exc}') from exc


def _validate(document: dict, ref: str) -> None:
    # Imported lazily to avoid a circular import with the validator module.
    from nodl_schema.validator import validate

    validate(document)


def _singular(category: str) -> str:
    return category[:-1] if category.endswith('s') else category


def _merge_into(dst: dict, src: dict, ref: str) -> None:
    """Merge ``src``'s entities into ``dst`` in place, erroring on any within-category name collision."""
    src_params = src.get('parameters') or {}
    if src_params:
        dst_params = dst.setdefault('parameters', {})
        for key, value in src_params.items():
            if key in dst_params:
                raise CompositionError(f"duplicate parameter '{key}' from include {ref!r}")
            dst_params[key] = value

    for category in _ENTITY_LIST_KEYS:
        src_list = src.get(category) or []
        if not src_list:
            continue
        dst_list = dst.setdefault(category, [])
        seen = {item.get('name') for item in dst_list}
        for item in src_list:
            name = item.get('name')
            if name in seen:
                raise CompositionError(f"duplicate {_singular(category)} '{name}' from include {ref!r}")
            seen.add(name)
            dst_list.append(item)
