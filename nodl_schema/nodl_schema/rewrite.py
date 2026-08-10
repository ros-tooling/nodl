# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Turning source-tree references into installed ones.

A ``local://`` reference is resolvable only while the source tree is present.
A consumer reading a document back out of the ament index gets text with no location, so nothing
in it can be relative to anything. Installation therefore has to replace each ``local://`` reference
with the ``nodl://`` reference naming the same document.

This is what ``ament_nodl`` calls at install time. It supplies the package being built and the
names its documents were registered under; everything about reference syntax stays here.
"""

from pathlib import Path

import yaml

from nodl_schema.composition import ResolutionError, normalize
from nodl_schema.local_resolver import PREFIX, is_absolute, ref_to_path
from nodl_schema.models import NodlDocument, Reference

_SUFFIXES = ('.yaml', '.yml', '.json')


def default_name(path: Path) -> str:
    """The name a document is assumed to be registered under: its filename without extensions."""
    name = path.name
    for suffix in _SUFFIXES:
        if name.endswith(suffix):
            name = name[: -len(suffix)]
            break
    return name[: -len('.nodl')] if name.endswith('.nodl') else name


def local_references(doc: NodlDocument, origin: str) -> list[Path]:
    """Every document reachable from ``doc`` through ``local://`` references, transitively.

    Returned in discovery order, deduplicated, and safe against cycles.
    ``ament_nodl`` uses this to check that referenced documents are registered, and to tell the
    build system which files a document depends on.
    """
    found: list[Path] = []
    _walk(doc, origin, found)
    return found


def includes_only(text: str) -> NodlDocument:
    """Parse just the ``include`` list out of document text, ignoring everything else.

    Collecting dependencies is a structural question, not a check, so this deliberately does not
    validate. A document that is malformed or invalid still has to report the files it depends on,
    and the real error belongs to the validation step rather than to this one. References that do
    not parse are skipped for the same reason.
    """
    data = yaml.safe_load(text)
    if not isinstance(data, dict):
        return NodlDocument()

    references = []
    for entry in data.get('include') or []:
        if not isinstance(entry, dict) or not entry.get('ref'):
            continue
        try:
            references.append(Reference(ref=entry['ref']))
        except Exception:
            continue
    return NodlDocument(include=references)


def _walk(doc: NodlDocument, origin: str, found: list[Path]) -> None:
    for reference in doc.include or []:
        if not reference.ref.startswith(PREFIX):
            continue
        child_ref = normalize(reference.ref, origin)
        path = ref_to_path(child_ref)
        if path in found:
            continue
        found.append(path)

        try:
            text = path.read_text(encoding='utf-8')
        except OSError as exc:
            raise ResolutionError(f'could not read {str(path)!r} for reference {reference.ref!r}: {exc}') from exc
        _walk(includes_only(text), child_ref, found)


def rewrite_local_references(
    doc: NodlDocument,
    *,
    origin: str,
    package: str,
    names: dict[Path, str] | None = None,
) -> NodlDocument:
    """Return a copy of ``doc`` with each ``local://`` reference replaced by its ``nodl://`` form.

    ``package`` is the package referenced documents belong to by default, and ``names`` maps a
    document's absolute path to the name it was registered as. A name may be given as
    ``<package>/<name>`` to point at a document registered under some other package, which is what
    a registration with a package override needs. A path missing from ``names`` is an error, since
    guessing would produce a reference to an index entry that may not exist.
    Pass ``names=None`` to fall back to each file's name, for callers with no registration record.

    ``nodl://`` references are left alone, and nothing else about the document changes, so the
    result differs from the authored document only in the spelling of its references.

    This does not recurse. Each document is rewritten by its own registration.
    """
    rewritten = doc.copy(deep=True)

    for reference in rewritten.include or []:
        if not reference.ref.startswith(PREFIX) or is_absolute(reference.ref):
            continue
        path = ref_to_path(normalize(reference.ref, origin))
        if names is None:
            name = default_name(path)
        elif path in names:
            name = names[path]
        else:
            raise ResolutionError(
                f'{reference.ref!r} resolves to {str(path)!r}, which is not registered. '
                f'Register it with ament_nodl_register_node before the document that includes it.'
            )
        # A name may already carry its own package, for a document registered under an override.
        target = name if '/' in name else f'{package}/{name}'
        reference.ref = f'nodl://{target}'

    return rewritten


def rewrite_file(
    source: Path,
    output: Path,
    *,
    package: str,
    names: dict[Path, str] | None = None,
) -> bool:
    """Write ``source`` to ``output`` with its ``local://`` references rewritten.

    Returns whether anything was rewritten. A document with no local references is copied byte for
    byte, so registering one is unaffected by any of this. Only a document that actually has a
    reference to rewrite is re-serialized, and then in the format its extension implies.
    """
    import shutil

    from nodl_schema.loader import dump_nodl, load_nodl
    from nodl_schema.local_resolver import path_to_ref

    output.parent.mkdir(parents=True, exist_ok=True)
    doc = load_nodl(source.read_text(encoding='utf-8'), resolve=False)

    if not any((reference.ref or '').startswith(PREFIX) for reference in doc.include or []):
        shutil.copyfile(source, output)
        return False

    rewritten = rewrite_local_references(doc, origin=path_to_ref(source), package=package, names=names)
    output.write_text(dump_nodl(rewritten, format='json' if source.suffix == '.json' else 'yaml'), encoding='utf-8')
    return True
