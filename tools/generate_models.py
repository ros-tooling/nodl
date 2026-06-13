#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Regenerate nodl_schema/nodl_schema/models.py from the JSON schema.

Run after editing any schema under nodl_schema/nodl_schema/schemas/ (node,
interface, or parameter). The pre-commit hook and CI both invoke this script.

Requires (pinned to match polymath_code_standard so the generated file is a
fixed point for the polymath-python pre-commit hook):
- datamodel-code-generator==0.25.9 (last version with pydantic v1 output)
- ruff==0.11.5
"""

from __future__ import annotations

import datetime
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_DIR = REPO_ROOT / 'nodl_schema' / 'nodl_schema' / 'schemas'
OUTPUT = REPO_ROOT / 'nodl_schema' / 'nodl_schema' / 'models.py'

# Mirrors polymath_code_standard/config/ruff.toml so the generated file passes
# the polymath-python hook without needing to be excluded. Keep in sync if
# polymath's config changes.
_RUFF_CONFIG_ARGS = [
    '--config',
    'line-length=120',
    '--config',
    'indent-width=4',
    '--config',
    'format.preview=true',
    '--config',
    'format.quote-style="single"',
    '--config',
    'format.indent-style="space"',
    '--config',
    'format.skip-magic-trailing-comma=false',
    '--config',
    'format.line-ending="lf"',
    '--config',
    'lint.select=["E4","E7","E9","F","I"]',
    '--config',
    'lint.fixable=["ALL"]',
]


def _copyright_header() -> str:
    return (
        f'# SPDX-FileCopyrightText: {datetime.date.today().year} '
        'Open Source Robotics Foundation, Inc.\n'
        '# SPDX-License-Identifier: Apache-2.0\n'
    )


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
        return f"""try:
    from pydantic.v1 import {names}
except ImportError:
    from pydantic import {names}"""

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
            elsewhere = source[: match.start()] + source[match.end() :]
            if re.search(rf'\b{re.escape(name)}\b', elsewhere):
                continue
            source = source[: match.start()] + source[match.end() :]
            removed = True
            break
        if not removed:
            return source


def _rewrite_cross_file_refs(node) -> None:
    """Rewrite cross-file $refs to local ``#/definitions/...``, in place.

    The node schema's ``main``/``mixins`` reference whole interface files and the
    interface schema references parameter definitions; both become local once the
    referenced schemas are folded into one ``definitions`` block (see _bundle_schema).
    """
    if isinstance(node, dict):
        for key, value in node.items():
            if key == '$ref' and isinstance(value, str):
                if value in ('interface.schema.yaml', 'interface.schema.yaml#'):
                    node[key] = '#/definitions/interface'
                elif '#/definitions/' in value and (
                    value.startswith('interface.schema.yaml') or value.startswith('parameter.schema.yaml')
                ):
                    node[key] = '#/definitions/' + value.split('#/definitions/', 1)[1]
            else:
                _rewrite_cross_file_refs(value)
    elif isinstance(node, list):
        for item in node:
            _rewrite_cross_file_refs(item)


def _bundle_schema() -> dict:
    """Fold node + interface + parameter schemas into one self-contained schema.

    datamodel-codegen emits a multi-module package for cross-file $refs, but a
    single ``models.py`` is what nodl_schema imports. So we root at the node
    schema and inline the interface (as a ``#/definitions/interface``) and all
    referenced definitions, then rewrite every cross-file ref to a local one.
    The result generates Node + Interface + every subtype into one file.
    """

    def load(name: str) -> dict:
        return yaml.safe_load((SCHEMA_DIR / name).read_text(encoding='utf-8'))

    node = load('node.schema.yaml')
    interface = load('interface.schema.yaml')
    parameter = load('parameter.schema.yaml')

    definitions: dict = {}
    # The interface's top-level object becomes the `interface` definition. Drop its
    # title so the generated class is named `Interface` (the key), not the title.
    definitions['interface'] = {
        k: v for k, v in interface.items() if k not in ('$schema', '$id', 'definitions', 'title')
    }
    definitions.update(interface.get('definitions', {}))
    definitions.update(parameter.get('definitions', {}))

    combined = {k: v for k, v in node.items() if k != '$id'}
    combined['definitions'] = definitions
    _rewrite_cross_file_refs(combined)
    return combined


def main() -> int:
    combined = _bundle_schema()
    with tempfile.NamedTemporaryFile('w', suffix='.json', delete=False) as tmp:
        json.dump(combined, tmp)
        bundle_path = tmp.name
    cmd = [
        'datamodel-codegen',
        '--input',
        bundle_path,
        '--input-file-type',
        'jsonschema',
        '--output',
        str(OUTPUT),
        '--output-model-type',
        'pydantic.BaseModel',
        '--target-python-version',
        '3.10',
        '--use-schema-description',
        '--use-standard-collections',
        '--collapse-root-models',
        '--class-name',
        'Node',
        '--disable-timestamp',
    ]
    try:
        result = subprocess.run(cmd)
    finally:
        Path(bundle_path).unlink(missing_ok=True)
    if result.returncode != 0:
        return result.returncode
    text = OUTPUT.read_text(encoding='utf-8')
    text = _strip_orphan_root_classes(text)
    text = _rewrite_pydantic_import(text)
    # The input was a temp bundle; point the provenance comment at the real root.
    text = re.sub(r'^#   filename:\s+.*$', '#   filename:  node.schema.yaml', text, count=1, flags=re.MULTILINE)
    OUTPUT.write_text(_copyright_header() + text)
    subprocess.run(['ruff', 'format', *_RUFF_CONFIG_ARGS, str(OUTPUT)], check=True)
    # ruff check may have residual lint findings that aren't auto-fixable; we
    # let it fix what it can and ignore its exit code so this script remains
    # reproducible. Anything left will surface as a polymath-python failure.
    subprocess.run(['ruff', 'check', '--fix', *_RUFF_CONFIG_ARGS, str(OUTPUT)], check=False)
    return 0


if __name__ == '__main__':
    sys.exit(main())
