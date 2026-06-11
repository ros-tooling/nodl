# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Sphinx configuration for the standalone (rosdoc2 / docs.ros.org) build of ros2nodl.

The combined nodl.readthedocs.io site does NOT use this file: it stages this package's doc/ tree into its own Sphinx
project (see nodl/doc/package_docs.py). This config only takes effect when rosdoc2 builds the package on its own.
"""

extensions = [
    'myst_parser',
    'sphinx.ext.intersphinx',
]

# Resolve {external+nodl:...} references against the published top-level site.
# rosdoc2 also seeds intersphinx from package.xml dependencies; this entry adds the top-level docs explicitly,
# since the metapackage that hosts them is not a build dependency of this package.
intersphinx_mapping = {
    'nodl': ('https://nodl.readthedocs.io/en/latest/', None),
}
