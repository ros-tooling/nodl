# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Sphinx configuration for the NoDL project documentation."""

import os

project = 'NoDL'
copyright = '2026, Open Source Robotics Foundation, Inc.'
author = 'NoDL contributors'

# Status banner; bump once the project stabilizes.
html_title = 'NoDL (v2, in development)'

extensions = [
    'myst_parser',
    'sphinx-jsonschema',
    'sphinx.ext.extlinks',
]

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

html_theme = 'sphinx_rtd_theme'
html_static_path = ['_static']
html_css_files = ['custom.css']

exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']
