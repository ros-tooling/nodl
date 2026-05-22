#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Regenerate nodl_schema/nodl_schema/models.py from the JSON schema.

Run after editing nodl_schema/nodl_schema/schemas/nodl.schema.yaml or
parameter.schema.yaml. The pre-commit hook and CI both invoke this script.

Requires datamodel-code-generator (not yet in rosdep; pip install separately).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA = REPO_ROOT / 'nodl_schema' / 'nodl_schema' / 'schemas' / 'nodl.schema.yaml'
OUTPUT = REPO_ROOT / 'nodl_schema' / 'nodl_schema' / 'models.py'


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
        'pydantic_v2.BaseModel',
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
    return result.returncode


if __name__ == '__main__':
    sys.exit(main())
