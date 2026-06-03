# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Sphinx configuration for the NoDL project documentation."""

import os
import sys

# Make this directory importable so the local schema_reference helper resolves.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import schema_reference

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


# -- Schema reference rendering ----------------------------------------------
# schema.md documents the canonical nodl_schema schemas via the sphinx-immaterial
# JSON domain; schema_reference.py prepares them (see setup() at the bottom).
# _generated/ is deliberately kept out of exclude_patterns so the domain can
# discover the mirrored files.
json_schemas = [schema_reference.SCHEMA_GLOB]
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


def setup(app):
    """Prepare the schema reference before the JSON domain reads the schemas."""
    schema_reference.mirror_schemas_for_docs()
    schema_reference.patch_object_value_type()
