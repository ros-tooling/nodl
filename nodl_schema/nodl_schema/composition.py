# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Resolution and merging of NoDL documents referenced by the ``include`` key.

A reference is a URI whose scheme selects a resolver.
Resolvers are registered, so which schemes work is a runtime property rather than a fixed list,
and the most recently registered resolver that handles a reference is the one used.

A resolver returns document text, not a path, since a reference need not name anything on a filesystem.
"""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Generator, Protocol, runtime_checkable

from nodl_schema.models import NodlDocument, ParameterDefinition

# --------------------------------
# Reference resolution
# --------------------------------


class ResolutionError(Exception):
    """Raised when includes cannot be resolved (unresolvable ref, cycle)."""


@runtime_checkable
class Resolver(Protocol):
    """Recognizes a form of NoDL reference and fetches its contents."""

    def handles(self, ref: str) -> bool:
        """Whether this resolver recognizes ``ref`` as a form it can resolve."""
        ...

    def resolve(self, ref: str, origin: Path | None = None) -> Path:
        """Return the path to the document ``ref`` names.
        Should only called when ``handles`` is true.
        Raise ResolutionError when ref cannot be resolved.
        @param ref: Exact text of the URI reference
        @param origin: Document that is making the reference - necessary to resolve local includes
        """
        ...


_RESOLVERS: list[Resolver] = list()


def register_resolver(resolver: Resolver) -> Resolver:
    """Register ``resolver`` for the rest of the process.

    Prefer :func:`resolver_registered` where the registration has a scope; this is for a
    resolver that belongs to the process, such as one a plugin installs at import time.
    """
    if not isinstance(resolver, Resolver):
        raise TypeError(f'{resolver!r} is not a Resolver')
    _RESOLVERS.append(resolver)
    return resolver


def unregister_resolver(resolver: Resolver) -> None:
    """Remove the registration of ``resolver``."""
    for index in range(len(_RESOLVERS) - 1, -1, -1):
        if _RESOLVERS[index] is resolver:
            del _RESOLVERS[index]
            return
    raise LookupError(f'{resolver!r} is not registered')


def get_resolvers() -> list[Resolver]:
    return _RESOLVERS


@contextmanager
def resolver_registered(resolver: Resolver) -> Generator[Resolver]:
    """Register ``resolver`` for the context, then remove it.

    This makes a resolver usable by tests.
    The resolver is in place for the block and gone afterward even on exception,
    so one test cannot leak a resolver into the next.
    """
    register_resolver(resolver)
    try:
        yield resolver
    finally:
        unregister_resolver(resolver)


def resolver_for(ref: str) -> Resolver | None:
    """The registered resolver that handles ``ref``, or None if nothing does."""
    for resolver in reversed(_RESOLVERS):
        if resolver.handles(ref):
            return resolver
    return None


def resolve(ref: str, origin: Path | None = None) -> Path:
    """Return the path to the document ``ref`` names, if it can be resolved."""
    resolver = resolver_for(ref)
    if resolver is None:
        raise ResolutionError(f'No registered resolver handles reference {ref!r}.')
    return resolver.resolve(ref, origin)


# --------------------------------
# Document merging
# --------------------------------


class MergeError(Exception):
    """Raised when documents cannot be merged (a name collision within one category)."""


def _collision(category: str, name: str, first: int, second: int) -> str:
    """Describe a collision, naming documents by position since that is their only identity here."""
    label = category.replace('_', ' ')
    where = 'the including document' if first == 0 else f'included document {first}'
    return f'duplicate {label} {name!r}: declared by {where} and by included document {second}'


def _merge_parameters(docs: list[NodlDocument]) -> dict[str, ParameterDefinition]:
    """Merge the parameter maps, erroring on a name declared by more than one document."""
    merged: dict[str, ParameterDefinition] = {}
    origin: dict[str, int] = {}

    for index, doc in enumerate(docs):
        for name, parameter in (doc.parameters or {}).items():
            if name in merged:
                raise MergeError(_collision('parameter', name, origin[name], index))
            merged[name] = parameter
            origin[name] = index

    return merged


def _merge_entities(docs: list[NodlDocument], field: str) -> list:
    """Concatenate one entity category across documents, erroring on a repeated name."""
    merged = []
    origin: dict[str, int] = {}

    for index, doc in enumerate(docs):
        for entity in getattr(doc, field) or []:
            if entity.name in origin:
                raise MergeError(_collision(field[:-1], entity.name, origin[entity.name], index))
            merged.append(entity)
            origin[entity.name] = index

    return merged


def merge_documents(docs: list[NodlDocument]) -> NodlDocument:
    """Combine documents into one.

    In the context of resolving includes, docs[0] is the root.

    Merging is strict.
    Two documents declaring the same name for the same entity type (publisher, parameter, etc) is an error,
    because the intent can't be determined here.

    ``nodl_version`` and ``description`` are taken from ``docs[0]``.
    The result has no ``include``, since it is the resolved form of one.
    """
    # Entity categories that merge as name-keyed lists. Parameters are a dict, and merge separately.
    _ENTITY_LIST_FIELDS = (
        'publishers',
        'subscriptions',
        'service_servers',
        'service_clients',
        'action_servers',
        'action_clients',
    )

    if not docs:
        raise ValueError('merge_documents needs at least one document')
    root = docs[0]

    return NodlDocument(
        nodl_version=root.nodl_version,
        description=root.description,
        include=None,
        parameters=_merge_parameters(docs) or None,
        **{field: _merge_entities(docs, field) or None for field in _ENTITY_LIST_FIELDS},
    )
