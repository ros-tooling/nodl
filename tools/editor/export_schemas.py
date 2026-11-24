#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Convert explicitly supplied YAML JSON Schemas to colocated JSON files."""

import argparse
import json
from pathlib import Path

import yaml


def export_schemas(sources: list[Path], output: Path) -> None:
    """Preserve schema contents, rewriting references to the supplied file names."""
    names = {source.name: source.with_suffix('.json').name for source in sources}

    def rewrite(value):
        if isinstance(value, list):
            return [rewrite(item) for item in value]
        if not isinstance(value, dict):
            return value
        result = {}
        for key, item in value.items():
            if key in ('$id', '$ref') and isinstance(item, str):
                filename, separator, fragment = item.partition('#')
                result[key] = names.get(filename, filename) + separator + fragment
            else:
                result[key] = rewrite(item)
        return result

    output.mkdir(parents=True, exist_ok=True)
    for source in sources:
        schema = rewrite(yaml.safe_load(source.read_text(encoding='utf-8')))
        (output / names[source.name]).write_text(
            json.dumps(schema, indent=2, ensure_ascii=False) + '\n', encoding='utf-8'
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('schemas', type=Path, nargs='+')
    args = parser.parse_args()
    export_schemas(args.schemas, args.output)


if __name__ == '__main__':
    main()
