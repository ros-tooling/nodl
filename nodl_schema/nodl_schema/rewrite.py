# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Rewrite references inside a NoDL document.

This is a general reference rewriter.
Given a set of ``FROM -> TO`` rewrites, it replaces matching references in a document's ``include`` list.
It knows nothing about packages, the ament index, or the build system.
A caller supplies the rewrites and decides what they mean.

The one scheme-aware detail is matching.
A ``local://`` reference is written relative to the document that holds it,
so the same target can appear as ``local://sibling.yaml`` in one document and as an absolute path in a rewrite rule.
References are therefore compared by canonical form:
a ``local://`` reference canonicalizes to its resolved absolute path, and any other scheme compares as written.
This lets ``local://`` includes be rewritten to ``nodl://`` index references,
but also plain ``nodl://a/b -> nodl://c/d`` renames, with the same mechanism.

The document is round-tripped through ruamel.yaml, so comments and key order survive.
Input may be YAML or JSON (JSON is valid YAML); output is always YAML.
"""

from __future__ import annotations

import io
from pathlib import Path

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedBase

from nodl_schema.composition import ResolutionError, resolver_for
from nodl_schema.loader import parse_nodl
from nodl_schema.local_resolver import LocalResolver


def _force_block_style(node) -> None:
    """Normalize a ruamel node tree to block style, so JSON (flow) input dumps as block YAML.

    Comments and quoting are unaffected; only the flow/block layout is changed.
    """
    if isinstance(node, CommentedBase):
        node.fa.set_block_style()
    if isinstance(node, dict):
        for value in node.values():
            _force_block_style(value)
    elif isinstance(node, list):
        for value in node:
            _force_block_style(value)


def _canonicalize(ref: str, origin: Path) -> str:
    resolver = resolver_for(ref)
    if not resolver:
        raise ResolutionError(f'No resolver registered for reference {ref}')
    return resolver.normalize(ref, origin)


def rewrite_references(source: Path, rewrites: dict[str, str]) -> str:
    """Return the text of ``source`` with its ``include`` references rewritten per ``rewrites``.

    ``rewrites`` maps a source reference to its replacement.
    A ``local://`` key is matched by resolved absolute path, so it should be given in absolute form.

    Raises the loader's validation errors when ``source`` is not a valid NoDL document.
    Raises :class:`ResolutionError` when any ``local://`` reference remains after rewriting,
    since such a reference does not resolve once the document is installed.
    """
    source = source.resolve()
    text = source.read_text()

    # Validate the input as a well-formed NoDL document before touching it.
    parse_nodl(text)

    yaml = YAML()
    # Wide enough not to wrap long scalars; indent so sequences sit under their key.
    # Older ruamel builds (humble/jazzy/kilted) mistype `width` as None, so pyright rejects the int there.
    yaml.width = 4096  # pyright: ignore[reportAttributeAccessIssue]
    yaml.indent(mapping=2, sequence=4, offset=2)
    data = yaml.load(text)

    canonical_rewrites = {_canonicalize(frm, source): to for frm, to in rewrites.items()}

    includes = data.get('include', [])
    for entry in includes:
        original = entry['ref']
        ref = _canonicalize(original, source)

        replacement = canonical_rewrites.get(ref)
        if replacement is None:
            # NOTE(emerson) this check bakes in a usage understanding that all local references must be rewritten
            if LocalResolver().handles(ref):
                raise ResolutionError(f'{source}: local reference {original} was not registered to rewrite')
        else:
            entry['ref'] = replacement

    _force_block_style(data)
    buffer = io.StringIO()
    yaml.dump(data, buffer)
    result = buffer.getvalue()

    return result
