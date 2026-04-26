"""Sphinx extension providing the ``.. nodl::`` directive.

Usage in conf.py::

    extensions = ['nodl_docgen.sphinx_ext']

Usage in RST::

    .. nodl:: path/to/my_node.nodl.yaml

The path is resolved relative to the directory containing the RST source file.

For rosdoc2 integration, add the extension to the package's Sphinx ``conf.py``
and use the directive wherever node interface documentation should appear.
"""
from __future__ import annotations

from pathlib import Path
from typing import List

from docutils import nodes
from docutils.statemachine import StringList

from sphinx.util.docutils import SphinxDirective


class NodlDirective(SphinxDirective):
    """Render a NoDL file as RST inline at the directive site."""

    required_arguments = 1
    optional_arguments = 0
    has_content = False
    option_spec = {}

    def run(self) -> List[nodes.Node]:
        nodl_arg = self.arguments[0]

        # Resolve path relative to the current source file's directory.
        src_file = Path(self.get_source_info()[0])
        full_path = (src_file.parent / nodl_arg).resolve()

        if not full_path.exists():
            msg = self.reporter.error(
                f'nodl: file not found: {full_path}',
                line=self.lineno,
            )
            return [msg]

        # Register the NoDL file as a dependency so Sphinx rebuilds when it changes.
        self.env.note_dependency(str(full_path))

        try:
            from nodl.schema import load_nodl
            from nodl_docgen._generator import generate_rst

            with open(full_path) as f:
                doc = load_nodl(f)

            rst_text = generate_rst(doc)
        except Exception as exc:  # noqa: BLE001
            msg = self.reporter.error(
                f'nodl: failed to generate RST from {full_path}: {exc}',
                line=self.lineno,
            )
            return [msg]

        # Parse the generated RST into docutils nodes and return them.
        container = nodes.section()
        self.state.nested_parse(
            StringList(rst_text.splitlines(), source=str(full_path)),
            self.content_offset,
            container,
        )
        return container.children


def setup(app):
    app.add_directive('nodl', NodlDirective)
    return {
        'version': '0.1.0',
        'parallel_read_safe': True,
        'parallel_write_safe': True,
    }
