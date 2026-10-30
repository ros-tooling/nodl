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
import xml.etree.ElementTree as ET
from pathlib import Path

from docutils import nodes
from sphinx import addnodes
from sphinx.environment import BuildEnvironment
from sphinx.util.docutils import SphinxDirective

_HERE = Path(__file__).parent
_REPO = _HERE / '..' / '..'
PACKAGES_DST = _HERE / '_generated' / 'packages'

# Packages that ship per-package docs, in the order they appear in the combined toctree.
# The ``nodl`` metapackage is documented by this top-level site itself; ``test_ament_nodl`` is a test fixture.
PACKAGES = [
    'nodl_schema',
    'nodl_observe',
    'ros2nodl',
    'ament_nodl',
    'nodl_common_interfaces',
    'nodl_generator_common',
    'nodl_generator_cpp',
    'nodl_generator_py',
    'nodl_runtime_py',
    'nodl_docgen',
]

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


def package_description(package_xml: Path) -> str:
    """Return a ``package.xml`` ``<description>`` as one line, with runs of whitespace collapsed."""
    if not package_xml.is_file():
        raise FileNotFoundError(f'{package_xml.parent.name} has no package.xml at {package_xml.resolve()}')
    element = ET.parse(package_xml).getroot().find('description')
    description = ' '.join((element.text or '').split()) if element is not None else ''
    if not description:
        raise ValueError(f'{package_xml.parent.name} has no <description> text in {package_xml.resolve()}')
    return description


def _package_xml(env: BuildEnvironment, pkg: str) -> Path:
    """Return a package's ``package.xml``, registered as a build dependency of the page being read."""
    package_xml = (_REPO / pkg / 'package.xml').resolve()
    env.note_dependency(str(package_xml))
    return package_xml


def package_page(pkg: str) -> str:
    """Return the docname of a package's staged landing page, absolute within the Sphinx source dir."""
    return f'/_generated/packages/{pkg}/overview'


class PackageList(SphinxDirective):
    """Render a bullet per documented package: its name linked to its overview page, then its ``package.xml`` description.

    Packages are listed alphabetically, and the sources are registered as build dependencies,
    so editing a description rebuilds the page that lists it.
    """

    def run(self) -> list[nodes.Node]:
        bullets = nodes.bullet_list()
        for pkg in sorted(PACKAGES):
            package_xml = _package_xml(self.env, pkg)
            link = addnodes.pending_xref(
                '',
                nodes.literal(pkg, pkg),
                refdomain='std',
                reftype='doc',
                reftarget=package_page(pkg),
                refdoc=self.env.docname,
                refexplicit=True,
                refwarn=True,
            )
            text = nodes.Text(f' \N{EM DASH} {package_description(package_xml)}')
            bullets += nodes.list_item('', nodes.paragraph('', '', link, text))
        return [bullets]


def package_description_role(name, rawtext, text, lineno, inliner, options=None, content=None):
    """Render the ``package.xml`` description of the package named by the role text, as in ``{package-description}`nodl```."""
    description = package_description(_package_xml(inliner.document.settings.env, text))
    return [nodes.Text(description)], []
