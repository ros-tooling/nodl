# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Sphinx configuration for the NoDL project documentation."""

project = 'NoDL'
copyright = '2026, Open Source Robotics Foundation, Inc.'
author = 'NoDL contributors'

# Status banner; bump once the project stabilizes.
html_title = 'NoDL (v2, in development)'

extensions = [
    'myst_parser',
    'sphinx-jsonschema',
]

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
