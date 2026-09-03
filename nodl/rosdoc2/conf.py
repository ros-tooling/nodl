# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Sphinx configuration for the standalone ``rosdoc2`` build of the ``nodl`` metapackage.

The prose documentation for the project is the combined site in ``nodl/doc``, built by Read the Docs.
That tree is not buildable here: it needs extensions no rosdoc2 environment installs,
and its package pages are staged at build time from the sibling packages in this repository.
So this build documents only what a metapackage has to say for itself, and links out for the rest.

``rosdoc2`` copies ``<package>/doc`` into every build whether or not it is the Sphinx source,
so that copy is excluded below rather than rendered into a broken half of the site.
"""

project = 'nodl'

exclude_patterns = [
    # Where the copy of `nodl/doc` lands, and the toctree stubs generated for it.
    # rosdoc2 has moved it between releases, so exclude both names it has used.
    'doc/**',
    'user_docs/**',
    'user_docs*.rst',
]
