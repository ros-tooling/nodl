# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
import argparse
import sys
from pathlib import Path

from nodl_docgen.markdown import render_markdown
from nodl_docgen.summarize import summarize_document
from nodl_schema.loader import load_nodl


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog='python -m nodl_docgen')
    parser.add_argument('nodl_doc', dest='doc', type=Path, help='Path to NoDL document to generate documentation for.')
    parser.add_argument('-o', '--output', type=Path, help='Path to write output to. If not provided, writes to stdout.')

    args = parser.parse_args(argv)

    doc = load_nodl(args.nodl_doc)
    summary = summarize_document(doc)
    content = render_markdown(summary)

    if args.output:
        with args.output.open('w') as f:
            f.write(content)
    else:
        print(content)


if __name__ == '__main__':
    sys.exit(main())
