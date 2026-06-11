# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Build-time staging of per-package ``doc/`` trees into the combined site.

Each shipped package authors its own ``<pkg>/doc/`` tree that is standalone-buildable by ``rosdoc2`` for docs.ros.org.
The combined Read the Docs site reuses those same sources by copying each tree under ``_generated/packages/<pkg>/``
(gitignored, like the schema mirror) so a single Sphinx project can list them in its toctree.

This is the same move ``schema_reference.mirror_schemas_for_docs`` makes: stage generated/external content beneath the
docs source dir so one build sees everything, without committing copies or symlinks.
"""

import shutil
from pathlib import Path

_HERE = Path(__file__).parent
_REPO = _HERE / '..' / '..'
PACKAGES_DST = _HERE / '_generated' / 'packages'

# Packages that ship per-package docs, in the order they appear in the combined toctree.
# The ``nodl`` metapackage is documented by this top-level site itself; ``test_ament_nodl`` is a test fixture.
PACKAGES = ['nodl_schema', 'ros2nodl', 'ament_nodl']

# Toctree entries, relative to the Sphinx source dir (== _HERE), mirrored by the "Packages" toctree in index.md.
# Each package's landing page is overview.md, not index.md: rosdoc2 reserves index for its own generated wrapper,
# and a user index.md there would shadow it and orphan the auto-generated API (see design/package_docs_proposal.md).
PACKAGE_TOCTREE_ENTRIES = [f'_generated/packages/{pkg}/overview' for pkg in PACKAGES]

# Files in a package's doc/ that are for the standalone rosdoc2 build only, not the combined Sphinx source.
_EXCLUDE = shutil.ignore_patterns('conf.py', '__pycache__', '_build')


def mirror_package_docs() -> None:
    """Copy each ``<pkg>/doc/`` tree into ``_generated/packages/<pkg>/`` for the combined build.

    Whole subtrees are copied so each package's internal relative links stay valid in the combined site.
    The per-package ``conf.py`` is skipped: the combined build uses this directory's ``conf.py``, and only
    the standalone rosdoc2 build reads the package-local one.
    """
    if PACKAGES_DST.exists():
        shutil.rmtree(PACKAGES_DST)
    for pkg in PACKAGES:
        src = _REPO / pkg / 'doc'
        if not src.is_dir():
            raise FileNotFoundError(f'{pkg} has no doc/ tree at {src.resolve()}')
        shutil.copytree(src, PACKAGES_DST / pkg, ignore=_EXCLUDE)
