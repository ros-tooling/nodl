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

# {repo}`path/to/file` renders as a GitHub blob link.
# READTHEDOCS_GIT_IDENTIFIER is set by Read the Docs to the branch/tag being built,
# so PR previews link to the PR's branch automatically.
# Local and GitHub Actions builds default to main via the fallback.
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

exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']
