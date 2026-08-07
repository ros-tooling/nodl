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
from typing import Iterator, Protocol, runtime_checkable

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
# Resource type under which ament_nodl_register_node publishes a document; the key is <package>__<name>.
_AMENT_RESOURCE_TYPE = 'nodl_nodes'


class CompositionError(Exception):
    """Raised when includes cannot be resolved or merged (unresolvable ref, cycle, or name collision)."""


@runtime_checkable
class Resolver(Protocol):
    """Recognizes a form of reference and turns it into the text of the document it names."""

    def handles(self, ref: str) -> bool:
        """Whether this resolver recognizes ``ref`` as a form it can resolve."""
        ...

    def resolve(self, ref: str) -> str:
        """Return the raw text of the document ``ref`` names. Only called when ``handles`` is true."""
        ...


class AmentIndexResolver:
    """Resolves ``nodl://<package>/<name>`` through the ament index."""

    def handles(self, ref: str) -> bool:
        return ref.startswith(_NODL_SCHEME)

    def resolve(self, ref: str) -> str:
        package, _, name = ref[len(_NODL_SCHEME) :].partition('/')
        if not package or not name:
            raise CompositionError(f'invalid reference {ref!r}: expected nodl://<package>/<name>')
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


class ResolverRegistry:
    """The set of reference forms that can currently be resolved.

    Resolvers are searched most-recently-registered first, so registering one shadows any
    already handling the same reference for as long as it stays registered.
    """

    def __init__(self, resolvers: tuple[Resolver, ...] = ()):
        self._resolvers: list[Resolver] = list(resolvers)

    def register(self, resolver: Resolver) -> Resolver:
        """Add ``resolver``, giving it precedence over those already registered."""
        if not isinstance(resolver, Resolver):
            raise TypeError(f'{resolver!r} is not a Resolver: it needs handles() and resolve() methods')
        self._resolvers.append(resolver)
        return resolver

    def unregister(self, resolver: Resolver) -> None:
        """Remove the most recent registration of ``resolver``.

        Removing the most recent one rather than the first keeps nesting well behaved: an
        inner scope that re-registers something already present undoes only its own addition.
        """
        for index in range(len(self._resolvers) - 1, -1, -1):
            if self._resolvers[index] is resolver:
                del self._resolvers[index]
                return
        raise LookupError(f'{resolver!r} is not registered')

    def resolver_for(self, ref: str) -> Resolver | None:
        """The registered resolver that handles ``ref``, or None if nothing does."""
        for resolver in reversed(self._resolvers):
            if resolver.handles(ref):
                return resolver
        return None

    def resolve(self, ref: str) -> str:
        """Return the text of the document ``ref`` names, via whichever resolver handles it."""
        resolver = self.resolver_for(ref)
        if resolver is None:
            raise CompositionError(
                f'no registered resolver handles reference {ref!r}; '
                f'the scheme selects the resolver, and nothing claims this one'
            )
        try:
            return resolver.resolve(ref)
        except CompositionError:
            raise
        except Exception as exc:
            raise CompositionError(f'could not resolve include {ref!r}: {exc}') from exc

    def __iter__(self) -> Iterator[Resolver]:
        """Iterate in registration order, oldest first (the reverse of search order)."""
        return iter(self._resolvers)

    def __len__(self) -> int:
        return len(self._resolvers)


# Process-wide, so registering a form makes it available to every load in the process rather
# than only to callers that were passed a resolver.
_REGISTRY = ResolverRegistry((AmentIndexResolver(),))


def default_registry() -> ResolverRegistry:
    """The registry ``resolve_document`` consults."""
    return _REGISTRY


def register_resolver(resolver: Resolver) -> Resolver:
    """Register ``resolver`` in the default registry for the rest of the process.

    Prefer :func:`resolver_registered` where the registration has a scope; this is for a
    resolver that belongs to the process, such as one a plugin installs at import time.
    """
    return _REGISTRY.register(resolver)


def unregister_resolver(resolver: Resolver) -> None:
    """Remove the most recent registration of ``resolver`` from the default registry."""
    _REGISTRY.unregister(resolver)


@contextmanager
def resolver_registered(resolver: Resolver) -> Iterator[Resolver]:
    """Register ``resolver`` for the duration of the block, then remove it.

    Scoping the registration is what keeps a process-wide registry usable from tests: the
    resolver is in place for anything the block loads, and gone afterwards even if the block
    raises, so one test cannot leak a resolver into the next.
    """
    register_resolver(resolver)
    try:
        yield resolver
    finally:
        unregister_resolver(resolver)


def resolve_document(data: dict, *, _stack: list[str] | None = None) -> dict:
    """Return a copy of ``data`` with its ``include`` list resolved and merged in.

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


def _validate(document: dict) -> None:
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
