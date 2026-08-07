# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Composition of NoDL documents via the ``include`` key.

A document may list other NoDL documents under ``include``; each reference is
resolved, validated, and its interface entities (parameters, publishers,
subscriptions, service/action servers and clients) are merged into the
including document. Includes are followed recursively, and a name collision
within any single category is an error.

A reference is a URI whose scheme selects a :class:`Resolver`. A resolver answers
two questions: whether it recognizes a reference (:meth:`~Resolver.handles`) and
what document text that reference names (:meth:`~Resolver.resolve`). Splitting
the two is what lets a :class:`ResolverRegistry` hold several and pick one, so
adding a reference form means registering a resolver rather than editing
anything here.

:class:`AmentIndexResolver` is registered by default and handles
``nodl://<package>/<name>``, looked up in the ament index as the resource
``nodl_nodes/<package>__<name>`` that ``ament_nodl_register_node`` installs.
Anything else registers into the same process-wide registry::

    with resolver_registered(MyResolver()):
        doc = load_nodl(source)

Registration is what makes a form available, rather than a resolver argument
threaded down through every caller: ``load_nodl`` and ``resolve_document`` take
no resolver, so a consumer that registers one changes what every load in the
process can reach. The registry searches most-recently-registered first, so a
scoped registration shadows a default one for as long as it is in place, which
is what lets a test stand in for the ament index without one being present.

``resolve`` deals in document text rather than paths: an ament index resource is
content, not a file a consumer is meant to locate, and a form fetching from
somewhere other than a filesystem would have no path to hand back. Nothing
downstream of the fetch inspects the reference that produced the text, so a
reference form is a fetch strategy and nothing more.
"""

from __future__ import annotations

import copy
from contextlib import contextmanager
from typing import Generator, Protocol, runtime_checkable

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

class ResolutionError(Exception):
    """Raised when includes cannot be resolved (unresolvable ref, cycle)."""


@runtime_checkable
class Resolver(Protocol):
    """Recognizes a form of NoDL reference and fetches its contents."""

    def handles(self, ref: str) -> bool:
        """Whether this resolver recognizes ``ref`` as a form it can resolve."""
        ...

    def resolve(self, ref: str) -> str:
        """Return the raw text of the document ``ref`` names. Only called when ``handles`` is true."""
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


@contextmanager
def resolver_registered(resolver: Resolver) -> Generator[Resolver]:
    """Register ``resolver`` for the context, then remove it.

    Scoping the registration is what keeps a process-wide registry usable from tests: the
    resolver is in place for anything the block loads, and gone afterwards even if the block
    raises, so one test cannot leak a resolver into the next.
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


def resolve(ref: str) -> str:
    """Return the text of the document ``ref`` names, if it can be resolved."""
    resolver = resolver_for(ref)
    if resolver is None:
        raise ResolutionError(f'No registered resolver handles reference {ref!r}.')
    return resolver.resolve(ref)


def resolve_document():
    """

    Each reference is fetched through whichever registered resolver handles it,
    schema-validated, recursively resolved, and merged. The returned dict has no ``include``
    key. The input ``data`` is not mutated.

    Raises ``CompositionError`` on a reference no resolver handles, an unresolvable
    reference, an include cycle, or a name collision within a category; raises
    ``jsonschema.ValidationError`` if an included document does not satisfy the schema.
    """
    stack = _stack or []

    result = copy.deepcopy(data)
    includes = result.pop('include', None) or []

    for entry in includes:
        ref = entry['ref']
        if ref in stack:
            chain = ' -> '.join([*stack, ref])
            raise CompositionError(f'include cycle detected: {chain}')

        text = _REGISTRY.resolve(ref)
        child = yaml.safe_load(text)
        if not isinstance(child, dict):
            raise CompositionError(f'included document {ref!r} is not a YAML/JSON mapping')

        _validate(child)
        resolved_child = resolve_document(child, _stack=[*stack, ref])
        _merge_into(result, resolved_child, ref)

    return result
