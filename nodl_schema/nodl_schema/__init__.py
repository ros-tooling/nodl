# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""NoDL schema, in-memory models, and validation helpers."""

from nodl_schema.ament_resolver import AmentIndexResolver
from nodl_schema.composition import (
    ResolutionError,
    Resolver,
    get_resolvers,
    register_resolver,
    resolver_registered,
    unregister_resolver,
)
from nodl_schema.loader import dump_nodl, load_nodl, load_nodl_with_doc_tree, parse_nodl, resolve_document
from nodl_schema.local_resolver import LocalResolver
from nodl_schema.validation import load_schema, validate

register_resolver(AmentIndexResolver())
register_resolver(LocalResolver())

__all__ = [
    'AmentIndexResolver',
    'ResolutionError',
    'Resolver',
    'dump_nodl',
    'load_nodl',
    'load_nodl_with_doc_tree',
    'load_schema',
    'get_resolvers',
    'parse_nodl',
    'register_resolver',
    'resolve_document',
    'resolver_registered',
    'unregister_resolver',
    'validate',
]
