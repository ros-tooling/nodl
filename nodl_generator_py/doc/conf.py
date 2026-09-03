# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Sphinx configuration for the standalone rosdoc2 build."""

extensions = [
    'myst_parser',
    'sphinx.ext.extlinks',
    'sphinx.ext.intersphinx',
]

intersphinx_mapping = {
    'nodl': ('https://nodl.readthedocs.io/en/latest/', None),
}

extlinks = {
    'repo': ('https://github.com/ros-tooling/nodl/blob/main/%s', '%s'),
}
