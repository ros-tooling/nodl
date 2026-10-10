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
from nodl_schema.conformance import Difference, DiffReport, diff, diff_report
from nodl_schema.ignore import IGNORE_KINDS, IgnoreRule
from nodl_schema.loader import (
    dump_nodl,
    load_nodl,
    load_nodl_with_doc_tree,
    load_schema,
    parse_nodl,
    resolve_document,
    validate,
)
from nodl_schema.local_resolver import LocalResolver
from nodl_schema.rewrite import UnrewrittenReferenceError, rewrite_references

register_resolver(AmentIndexResolver())
register_resolver(LocalResolver())

__all__ = [
    'AmentIndexResolver',
    'IGNORE_KINDS',
    'DiffReport',
    'Difference',
    'IgnoreRule',
    'ResolutionError',
    'Resolver',
    'UnrewrittenReferenceError',
    'dump_nodl',
    'diff',
    'diff_report',
    'load_nodl',
    'load_nodl_with_doc_tree',
    'load_schema',
    'get_resolvers',
    'parse_nodl',
    'register_resolver',
    'resolve_document',
    'resolver_registered',
    'rewrite_references',
    'unregister_resolver',
    'validate',
]
