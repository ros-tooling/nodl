#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Regenerate nodl_schema/nodl_schema/models.py from the JSON schema.

Run after editing nodl_schema/nodl_schema/schemas/nodl.schema.yaml or
parameter.schema.yaml. The pre-commit hook and CI both invoke this script.

Requires datamodel-code-generator (not yet in rosdep; pip install separately).
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA = REPO_ROOT / 'nodl_schema' / 'nodl_schema' / 'schemas' / 'nodl.schema.yaml'
OUTPUT = REPO_ROOT / 'nodl_schema' / 'nodl_schema' / 'models.py'


_PYDANTIC_IMPORT_LINE = re.compile(r'^from pydantic import (.+)$', re.MULTILINE)


def _rewrite_pydantic_import(source: str) -> str:
    """Redirect ``from pydantic import ...`` through the ``pydantic.v1`` shim
    when available, so the v1-style generated code works on pydantic v2 too.

    On pydantic v1 the ``pydantic.v1`` submodule does not exist, so the import
    falls through to the top-level ``pydantic`` module. On pydantic v2 the
    ``pydantic.v1`` submodule is the v1 compatibility shim and exposes
    BaseModel/Extra/constr with v1 semantics.
    """
    def replace(match: re.Match) -> str:
        names = match.group(1)
        return (
            f'try:\n'
            f'    from pydantic.v1 import {names}\n'
            f'except ImportError:\n'
            f'    from pydantic import {names}'
        )
    return _PYDANTIC_IMPORT_LINE.sub(replace, source, count=1)


def _strip_orphan_root_classes(source: str) -> str:
    """Delete BaseModel classes whose only field is ``__root__`` and that are
    never referenced elsewhere in the file.

    --collapse-root-models inlines all uses of root types, but the generator
    still emits the original class definition. Those orphan classes use the
    ``__root__`` field syntax, which pydantic v2 rejects with a TypeError.
    Stripping them keeps the output usable on both v1 (humble/jazzy/kilted)
    and v2 (lyrical+).
    """
    class_pattern = re.compile(
        r'^class (\w+)\(BaseModel\):\n((?:    .*\n|\n)+?)(?=^class |\Z)',
        re.MULTILINE,
    )
    while True:
        removed = False
        for match in class_pattern.finditer(source):
            name, body = match.group(1), match.group(2)
            if '__root__:' not in body:
                continue
            # Reference check: name used anywhere outside its own definition.
            elsewhere = source[: match.start()] + source[match.end():]
            if re.search(rf'\b{re.escape(name)}\b', elsewhere):
                continue
            source = source[: match.start()] + source[match.end():]
            removed = True
            break
        if not removed:
            return source


def main() -> int:
    cmd = [
        'datamodel-codegen',
        '--input',
        str(SCHEMA),
        '--input-file-type',
        'jsonschema',
        '--output',
        str(OUTPUT),
        '--output-model-type',
        'pydantic.BaseModel',
        '--target-python-version',
        '3.10',
        '--use-schema-description',
        '--use-double-quotes',
        '--use-standard-collections',
        '--use-union-operator',
        '--collapse-root-models',
        '--class-name',
        'NodlDocument',
        '--disable-timestamp',
    ]
    result = subprocess.run(cmd)
    if result.returncode != 0:
        return result.returncode
    text = OUTPUT.read_text(encoding='utf-8')
    text = _strip_orphan_root_classes(text)
    text = _rewrite_pydantic_import(text)
    OUTPUT.write_text(text)
    return 0


if __name__ == '__main__':
    sys.exit(main())
