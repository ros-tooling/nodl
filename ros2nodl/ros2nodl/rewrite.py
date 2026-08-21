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

from nodl_schema import parse_nodl

_LOCAL_PREFIX = 'local://'


class RewriteError(Exception):
    """Raised when a document's references cannot be rewritten."""


def parse_reference_arg(arg: str) -> tuple[str, str]:
    """Parse a ``FROM:=TO`` rewrite rule into its two references.

    ``:=`` separates the two; neither reference contains it, so the split is unambiguous.
    """
    frm, sep, to = arg.partition(':=')
    if not sep or not frm or not to:
        raise RewriteError(f'invalid reference rule {arg!r}: expected FROM:=TO')
    return frm, to


def _canonical_ref(ref: str, origin: Path | None) -> str:
    """Canonicalize ``ref`` for comparison.

    A ``local://`` reference resolves to an absolute path, relative to ``origin``'s directory when the reference itself is relative,
    so the same target matches however it was written.
    Any other scheme is returned unchanged.
    """
    if not ref.startswith(_LOCAL_PREFIX):
        return ref
    rel = ref[len(_LOCAL_PREFIX) :]
    base = origin.parent if origin is not None else Path.cwd()
    return _LOCAL_PREFIX + str((base / rel).resolve())


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


def rewrite_references(source: Path, rewrites: dict[str, str]) -> str:
    """Return the text of ``source`` with its ``include`` references rewritten per ``rewrites``.

    ``rewrites`` maps a source reference to its replacement.
    A ``local://`` key is matched by resolved absolute path, so it should be given in absolute form.

    Raises the loader's validation errors when ``source`` is not a valid NoDL document.
    Raises :class:`RewriteError` when any ``local://`` reference remains after rewriting,
    since such a reference does not resolve once the document is installed.
    """
    source = source.resolve()
    text = source.read_text()

    # Validate the input as a well-formed NoDL document before touching it.
    parse_nodl(text)

    yaml = YAML()
    # Wide enough not to wrap long scalars; indent so sequences sit under their key.
    yaml.width = 4096
    yaml.indent(mapping=2, sequence=4, offset=2)
    data = yaml.load(text)

    # The FROM side is origin-independent (local:// keys are absolute); canonicalize it once.
    canonical = {_canonical_ref(frm, None): to for frm, to in rewrites.items()}

    includes = data.get('include') if isinstance(data, dict) else None
    for entry in includes or []:
        ref = entry.get('ref') if hasattr(entry, 'get') else None
        if ref is None:
            continue
        replacement = canonical.get(_canonical_ref(ref, source))
        if replacement is not None:
            entry['ref'] = replacement

    _force_block_style(data)
    buffer = io.StringIO()
    yaml.dump(data, buffer)
    result = buffer.getvalue()

    # A document must be self-contained once installed: no local:// reference may survive.
    rewritten = parse_nodl(result)
    stragglers = [r.ref for r in (rewritten.include or []) if r.ref.startswith(_LOCAL_PREFIX)]
    if stragglers:
        raise RewriteError(
            f'{source}: unresolved local reference(s) after rewrite: {stragglers}; '
            f'ensure each local:// target is registered'
        )

    return result
