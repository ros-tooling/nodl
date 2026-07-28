# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Composition of NoDL documents via the ``include`` key.

A document may list other NoDL documents under ``include``; each reference is
resolved, validated, and its interface entities (parameters, publishers,
subscriptions, service/action servers and clients) are merged into the
including document. Includes are followed recursively, and a name collision
within any single category is an error.

Resolution is pluggable through the ``Resolver`` protocol so callers (and tests)
can supply their own lookup. ``DefaultResolver`` handles the two reference forms
the schema accepts:

* ``nodl://<package>/<name>`` -- looked up in the ament index as the resource
  ``nodl_nodes/<package>__<name>`` that ``ament_nodl_register_node`` installs.
* ``http://`` / ``https://`` -- fetched over the network.
"""

from __future__ import annotations

import copy
from typing import Protocol, runtime_checkable

import yaml

# Timeout, in seconds, for fetching an http(s) reference. Kept finite so a build-time
# resolvability check cannot hang the build indefinitely on an unreachable host.
_HTTP_TIMEOUT = 30

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
# Resource type under which ament_nodl_register_node publishes a document; the key is <package>__<name>.
_AMENT_RESOURCE_TYPE = 'nodl_nodes'


class CompositionError(Exception):
    """Raised when includes cannot be resolved or merged (unresolvable ref, cycle, or name collision)."""


@runtime_checkable
class Resolver(Protocol):
    """Turns a reference string into the raw text of the referenced NoDL document."""

    def fetch(self, ref: str) -> str: ...


class DefaultResolver:
    """Resolves ``nodl://`` references through the ament index and ``http(s)://`` over the network."""

    def fetch(self, ref: str) -> str:
        if ref.startswith(_NODL_SCHEME):
            return self._fetch_ament(ref)
        if ref.startswith('http://') or ref.startswith('https://'):
            return self._fetch_http(ref)
        raise CompositionError(f'unsupported reference scheme: {ref!r} (expected nodl://, http://, or https://)')

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

    def _fetch_http(self, ref: str) -> str:
        from urllib.request import urlopen

        try:
            with urlopen(ref, timeout=_HTTP_TIMEOUT) as response:  # noqa: S310 - scheme is checked above
                return response.read().decode('utf-8')
        except Exception as exc:
            raise CompositionError(f'could not fetch {ref!r}: {exc}') from exc


def resolve_document(data: dict, resolver: Resolver | None = None, *, _stack: list[str] | None = None) -> dict:
    """Return a copy of ``data`` with its ``include`` list resolved and merged in.

    Each referenced document is fetched via ``resolver`` (``DefaultResolver`` if none is
    given), schema-validated, recursively resolved, and merged. The returned dict has no
    ``include`` key. The input ``data`` is not mutated.

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
        ref = entry['ref']
        if ref in stack:
            chain = ' -> '.join([*stack, ref])
            raise CompositionError(f'include cycle detected: {chain}')

        text = _fetch(resolver, ref)
        child = yaml.safe_load(text)
        if not isinstance(child, dict):
            raise CompositionError(f'included document {ref!r} is not a YAML/JSON mapping')

        _validate(child, ref)
        resolved_child = resolve_document(child, resolver, _stack=[*stack, ref])
        _merge_into(result, resolved_child, ref)

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
