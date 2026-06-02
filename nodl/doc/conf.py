# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Sphinx configuration for the NoDL project documentation."""

import os
import shutil
from pathlib import Path

project = 'NoDL'
copyright = '2026, Open Source Robotics Foundation, Inc.'
author = 'NoDL contributors'

# Status banner; bump once the project stabilizes.
html_title = 'NoDL (v2, in development)'

extensions = [
    'myst_parser',
    'sphinx_immaterial',
    'sphinx_immaterial.apidoc.json.domain',
    'sphinx.ext.extlinks',
]

# -- Schema sources ----------------------------------------------------------
# The canonical schemas live in the nodl_schema package. The immaterial JSON
# domain only discovers files beneath this docs source dir, so mirror them into
# _generated/ at build time. Schemas are keyed by their `$id` (a URL), not their
# path, so the copy doesn't affect `$ref` resolution between them.
_DOC_DIR = Path(__file__).parent.resolve()
_SCHEMA_SRC = _DOC_DIR / '..' / '..' / 'nodl_schema' / 'nodl_schema' / 'schemas'
_SCHEMA_DST = _DOC_DIR / '_generated' / 'schemas'
_SCHEMA_DST.mkdir(parents=True, exist_ok=True)
for _schema in _SCHEMA_SRC.glob('*.schema.yaml'):
    shutil.copy2(_schema, _SCHEMA_DST / _schema.name)

# Patterns are relative to this source dir; the domain skips anything in
# exclude_patterns, so _generated/ is intentionally left out of those.
json_schemas = ['_generated/schemas/*.yaml']
json_schema_validate = True

# -- GitHub source links -----------------------------------------------------
if os.environ.get('READTHEDOCS_VERSION_TYPE') == 'external':
    # For PR builds RTD sets it to the PR number, which is not a valid GitHub ref, so we substitute the commit SHA instead.
    _repo_ref = os.environ.get('READTHEDOCS_GIT_COMMIT_HASH', 'main')
else:
    # For branch/tag builds (including local/GitHub Actions), this is the readable ref name.
    _repo_ref = os.environ.get('READTHEDOCS_GIT_IDENTIFIER', 'main')

extlinks = {
    'repo': (f'https://github.com/ros-tooling/nodl/blob/{_repo_ref}/%s', '%s'),
}

myst_enable_extensions = [
    'colon_fence',
    'deflist',
    'fieldlist',
    'tasklist',
]

source_suffix = {
    '.md': 'markdown',
    '.rst': 'restructuredtext',
}

# -- HTML output (sphinx-immaterial) -----------------------------------------
html_theme = 'sphinx_immaterial'
html_theme_options = {
    'icon': {'repo': 'fontawesome/brands/github'},
    'repo_url': 'https://github.com/ros-tooling/nodl',
    'repo_name': 'ros-tooling/nodl',
    'edit_uri': f'blob/{_repo_ref}/nodl/doc',
    'features': [
        'navigation.expand',
        'navigation.top',
        'toc.follow',
        'search.highlight',
        'search.share',
        'content.code.copy',
    ],
    'palette': [
        {
            'media': '(prefers-color-scheme: light)',
            'scheme': 'default',
            'primary': 'blue',
            'accent': 'light-blue',
            'toggle': {
                'icon': 'material/lightbulb-outline',
                'name': 'Switch to dark mode',
            },
        },
        {
            'media': '(prefers-color-scheme: dark)',
            'scheme': 'slate',
            'primary': 'blue',
            'accent': 'light-blue',
            'toggle': {
                'icon': 'material/lightbulb',
                'name': 'Switch to light mode',
            },
        },
    ],
}

exclude_patterns = ['_build', '.venv', 'Thumbs.db', '.DS_Store']
