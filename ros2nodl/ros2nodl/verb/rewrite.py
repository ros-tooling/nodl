# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""``ros2 nodl rewrite`` -- rewrite references within a NoDL document."""

import sys
from pathlib import Path

from nodl_schema.rewrite import UnrewrittenReferenceError, rewrite_references
from ros2nodl.verb import VerbExtension


def parse_reference_arg(arg: str) -> tuple[str, str]:
    """Parse a ``FROM:=TO`` rewrite rule into its two references.

    ``:=`` separates the two; neither reference contains it, so the split is unambiguous.
    """
    frm, sep, to = arg.partition(':=')
    if not sep or not frm or not to:
        raise ValueError(f'invalid reference rule {arg!r}: expected FROM:=TO')
    return frm, to


# argparse exits with 2 for usage errors, so a distinct status marks an unrewritten reference.
EXIT_UNREWRITTEN_REFERENCE = 3


class RewriteVerb(VerbExtension):
    """Rewrite references in a NoDL document, such as local:// includes to nodl:// index references for install.

    Exits 3 when a local:// include has no rewrite rule, and 1 for any other failure.
    """

    def add_arguments(self, parser, cli_name):
        parser.add_argument('source', type=Path, help='NoDL document to rewrite.')
        parser.add_argument(
            '-r',
            '--reference',
            dest='references',
            action='append',
            default=[],
            metavar='FROM:=TO',
            help='Rewrite reference FROM to TO. Repeatable. A local:// FROM matches by resolved absolute path.',
        )
        mode = parser.add_mutually_exclusive_group(required=True)
        mode.add_argument(
            '-o',
            '--output',
            type=Path,
            help='Where to write the rewritten document.',
        )
        mode.add_argument(
            '--check',
            action='store_true',
            help='Write nothing, only check that every local:// include has a rewrite rule.',
        )

    def main(self, *, args) -> int:
        try:
            rewrites = dict(parse_reference_arg(rule) for rule in args.references)
            result = rewrite_references(args.source, rewrites)
            if not args.check:
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_text(result)
        except UnrewrittenReferenceError as exc:
            print(exc, file=sys.stderr)
            return EXIT_UNREWRITTEN_REFERENCE
        except Exception as exc:
            print(f'{args.source}: {exc}', file=sys.stderr)
            return 1
        return 0
