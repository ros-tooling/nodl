# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Sphinx configuration for the standalone ``rosdoc2`` build of the ``nodl`` metapackage.

Separate from the Read the Docs site in ``nodl/doc``.
"""

project = 'nodl'

exclude_patterns = [
    # rosdoc2 copies doc/ no matter what, so explicitly exclude it from this build.
    'doc/**',
    'user_docs/**',
    'user_docs*.rst',
]
