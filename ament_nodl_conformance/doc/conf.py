# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Sphinx configuration for standalone ament_nodl_conformance documentation."""

extensions = [
    'myst_parser',
    'sphinx.ext.intersphinx',
    'sphinx.ext.extlinks',
]

intersphinx_mapping = {
    'nodl': ('https://nodl.readthedocs.io/en/latest/', None),
}

extlinks = {
    'repo': ('https://github.com/ros-tooling/nodl/blob/main/%s', '%s'),
}
