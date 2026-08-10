# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
import argparse
import sys
from pathlib import Path

from nodl_schema.loader import load_nodl
from nodl_schema.local_resolver import path_to_ref
from nodl_schema.rewrite import includes_only, local_references, rewrite_file


def main(argv: list[str] | None = None) -> int:
    """``python -m nodl_schema <file>`` -- load and validate a NoDL file.

    Exits 0 on success, 1 on validation failure or I/O error.

    Includes are resolved by default, so validating a document also checks that its references resolve.

    Two other modes serve installation rather than authors.
    ``--list-references`` reports the source-tree documents a document depends on.
    ``--rewrite-to`` emits a copy whose ``local://`` references have become ``nodl://`` ones.
    """
    parser = argparse.ArgumentParser(
        prog='python -m nodl_schema',
        description='Validate a NoDL file against the schema.',
    )
    parser.add_argument('file', type=Path, help='Path to the NoDL file to validate.')
    parser.add_argument(
        '--no-resolve',
        dest='resolve',
        action='store_false',
        help='Validate the schema only; do not resolve include references. '
        'By default includes are resolved so the file is checked for resolvability too.',
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        '--list-references',
        action='store_true',
        help='Print the documents reachable through local:// references, transitively, '
        'one absolute path per line, instead of validating.',
    )
    mode.add_argument(
        '--rewrite-to',
        type=Path,
        metavar='PATH',
        help='Write a copy of the file to PATH with each local:// reference rewritten to '
        'nodl://<package>/<name>, instead of validating.',
    )
    parser.add_argument('--package', help='Package the rewritten references name. Used with --rewrite-to.')
    parser.add_argument(
        '--map',
        action='append',
        default=[],
        metavar='PATH=NAME',
        help='What a referenced document was registered as. Repeatable. Used with --rewrite-to.',
    )
    args = parser.parse_args(argv)

    try:
        if args.list_references:
            return _list_references(args.file)
        if args.rewrite_to is not None:
            return _rewrite(args.file, args.rewrite_to, args.package, args.map)
        with args.file.open('r') as f:
            load_nodl(f, resolve=args.resolve)
    except Exception as exc:
        print(f'{args.file}: {exc}', file=sys.stderr)
        return 1

    print(f'{args.file}: ok')
    return 0


def _list_references(file: Path) -> int:
    # Deliberately unvalidated: this reports what a document depends on, and a document that does
    # not validate still has dependencies. Validation is a separate run.
    doc = includes_only(file.read_text(encoding='utf-8'))
    for path in local_references(doc, path_to_ref(file)):
        print(path)
    return 0


def _rewrite(file: Path, output: Path, package: str | None, mappings: list[str]) -> int:
    if not package:
        raise ValueError('--package is required with --rewrite-to')

    names: dict[Path, str] = {}
    for item in mappings:
        path_text, separator, name = item.partition('=')
        if not separator or not path_text or not name:
            raise ValueError(f'malformed --map {item!r}: expected <path>=<name>')
        names[Path(path_text).resolve()] = name

    rewrite_file(file, output, package=package, names=names)
    print(f'{file}: ok')
    return 0
