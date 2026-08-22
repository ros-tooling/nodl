# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Sphinx rendering of NoDL documents.

Adding ``'nodl_sphinx'`` to a project's ``extensions`` registers the ``nodl-node`` directive.

The summary core is deliberately not re-exported here, and Sphinx is imported only inside :func:`setup`,
so ``nodl_sphinx.summarize`` stays importable without Sphinx installed.
"""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sphinx.application import Sphinx

# Mirrors the version in package.xml.
__version__ = '0.0.0'


def setup(app: 'Sphinx') -> dict[str, Any]:
    """Register the extension's directives with ``app``.

    Rendering reads the NoDL file and writes only its own nodes, sharing nothing between documents,
    so reading and writing are both parallel safe.
    """
    from nodl_sphinx.directives import NodlNodeDirective

    app.add_directive('nodl-node', NodlNodeDirective)

    return {
        'version': __version__,
        'parallel_read_safe': True,
        'parallel_write_safe': True,
    }
