# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Sphinx extension that gives the ``cmake:command`` directive typed fields.

``sphinxcontrib.moderncmakedomain`` defines no doc fields, so ``:param X:`` and ``:type X:`` render as unrelated rows.
This replaces the domain's ``command`` directive with a subclass that merges them, as the Python domain does.
"""

from sphinx.application import Sphinx
from sphinx.util.docfields import GroupedField, TypedField
from sphinxcontrib.moderncmakedomain.cmake import CMakeObject


class CMakeCommand(CMakeObject):
    doc_field_types = [
        TypedField('parameter', label='Parameters', names=('param',), typenames=('type',), can_collapse=True),
        GroupedField('keyword', label='Keywords', names=('keyword',), can_collapse=True),
        GroupedField('outvar', label='Output variables', names=('outvar',), can_collapse=True),
    ]


def setup(app: Sphinx) -> dict[str, bool]:
    app.setup_extension('sphinxcontrib.moderncmakedomain')
    app.add_directive_to_domain('cmake', 'command', CMakeCommand, override=True)
    return {'parallel_read_safe': True, 'parallel_write_safe': True}
