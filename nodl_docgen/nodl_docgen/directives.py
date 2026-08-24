# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""The ``nodl-node`` directive: a NoDL document rendered into a page as docutils nodes.

The rendering is a function from a :class:`~nodl_docgen.summarize.NodeSummary` to a titled section,
so it can be exercised with a summary and a docutils import, and nothing else.
The directive around it only finds the file, loads it, and hands the summary over.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Generic, Sequence, TypeVar

from docutils import nodes
from docutils.parsers.rst import directives
from sphinx.util.docutils import SphinxDirective

from nodl_docgen.summarize import ActionRow, EndpointRow, NodeSummary, ParameterRow, summarize_tree
from nodl_schema import load_nodl_with_doc_tree
from nodl_schema.composition import resolve, resolver_for
from nodl_schema.loader import DocumentTree, IncludedDocument

# --------------------------------
# Cells
# --------------------------------


def code_cell(text: str) -> list[nodes.Node]:
    """A cell holding one code span, for a name, a type, or a value.

    Empty text yields an empty cell rather than an empty code span,
    so a column that nothing fills in can be recognized and dropped.
    """
    return [nodes.literal(text, text)] if text else []


def parameter_description_cell(row: ParameterRow) -> list[nodes.Node]:
    """A parameter's prose, its validator constraints as a list, and any prose constraints after them.

    The constraints live with the description because they are what the description would otherwise have to say.
    """
    return [
        *paragraphs(row.description),
        *([bullet_list(row.constraints)] if row.constraints else []),
        *paragraphs(row.additional_constraints),
    ]


def paragraphs(text: str) -> list[nodes.paragraph]:
    """One paragraph per blank-line-separated block of ``text``, and nothing at all for empty text."""
    return [nodes.paragraph(block, block) for block in re.split(r'\n\s*\n', text.strip()) if block]


def prose_item(text: str) -> nodes.paragraph:
    """One line of prose as a list item's body."""
    return nodes.paragraph(text, text)


def code_item(text: str) -> nodes.paragraph:
    """One code span as a list item's body, for a name that is a reference rather than prose."""
    paragraph = nodes.paragraph()
    paragraph += code_cell(text)
    return paragraph


def bullet_list(items: Sequence[str], item: Callable[[str], nodes.Node] = prose_item) -> nodes.bullet_list:
    """A bullet list of one-line items, each drawn by ``item``."""
    listing = nodes.bullet_list()
    for text in items:
        entry = nodes.list_item()
        entry += item(text)
        listing += entry
    return listing


# --------------------------------
# Tables
# --------------------------------

RowT = TypeVar('RowT')


@dataclass(frozen=True)
class Column(Generic[RowT]):
    """One table column: its heading, and how a row fills its cell.

    A column that no row fills in is dropped, unless it is ``always`` present.
    That keeps a QoS column off a table of services that declare none,
    without making the column set depend on which category is being drawn.
    """

    header: str
    cell: Callable[[RowT], Sequence[nodes.Node]]
    always: bool = False


def build_table(columns: Sequence[Column[RowT]], rows: Sequence[RowT]) -> nodes.table:
    """A table of ``rows``, one column per entry in ``columns`` that has something to show."""
    cells = [[column.cell(row) for column in columns] for row in rows]
    shown = [index for index, column in enumerate(columns) if column.always or any(row[index] for row in cells)]

    group = nodes.tgroup(cols=len(shown))
    for _ in shown:
        group += nodes.colspec(colwidth=1)
    group += _table_head([columns[index].header for index in shown])
    group += _table_body([[row[index] for index in shown] for row in cells])

    table = nodes.table()
    table += group
    return table


def _table_head(headers: Sequence[str]) -> nodes.thead:
    head = nodes.thead()
    head += _table_row([[nodes.paragraph(header, header)] for header in headers])
    return head


def _table_body(rows: Sequence[Sequence[Sequence[nodes.Node]]]) -> nodes.tbody:
    body = nodes.tbody()
    for cells in rows:
        body += _table_row(cells)
    return body


def _table_row(cells: Sequence[Sequence[nodes.Node]]) -> nodes.row:
    row = nodes.row()
    for content in cells:
        entry = nodes.entry()
        entry += content
        row += entry
    return row


PARAMETER_COLUMNS: tuple[Column[ParameterRow], ...] = (
    Column('Name', lambda row: code_cell(row.name), always=True),
    Column('Type', lambda row: code_cell(row.type), always=True),
    Column('Default', lambda row: code_cell(row.default)),
    Column('Read-only', lambda row: paragraphs(row.read_only)),
    Column('Description', parameter_description_cell),
)

ENDPOINT_COLUMNS: tuple[Column[EndpointRow], ...] = (
    Column('Name', lambda row: code_cell(row.name), always=True),
    Column('Type', lambda row: code_cell(row.type), always=True),
    Column('QoS', lambda row: paragraphs(row.qos)),
    Column('Description', lambda row: paragraphs(row.description)),
)

ACTION_COLUMNS: tuple[Column[ActionRow], ...] = (
    Column('Name', lambda row: code_cell(row.name), always=True),
    Column('Type', lambda row: code_cell(row.type), always=True),
    Column('Description', lambda row: paragraphs(row.description)),
)


# --------------------------------
# Sections
# --------------------------------


@dataclass(frozen=True)
class Category(Generic[RowT]):
    """One interface category of a summary: its heading, how to read its rows, and how to tabulate them."""

    title: str
    rows: Callable[[NodeSummary], Sequence[RowT]]
    columns: tuple[Column[RowT], ...]


# Order is the order a reader meets the node: what it is configured with, then what it talks to.
CATEGORIES: tuple[Category[Any], ...] = (
    Category('Parameters', lambda summary: summary.parameters, PARAMETER_COLUMNS),
    Category('Publishers', lambda summary: summary.publishers, ENDPOINT_COLUMNS),
    Category('Subscriptions', lambda summary: summary.subscriptions, ENDPOINT_COLUMNS),
    Category('Service Servers', lambda summary: summary.service_servers, ENDPOINT_COLUMNS),
    Category('Service Clients', lambda summary: summary.service_clients, ENDPOINT_COLUMNS),
    Category('Action Servers', lambda summary: summary.action_servers, ACTION_COLUMNS),
    Category('Action Clients', lambda summary: summary.action_clients, ACTION_COLUMNS),
)


def build_section(title: str, body: Sequence[nodes.Node]) -> nodes.section:
    """A titled section holding ``body``.

    The section carries a name but no id.
    Ids belong to whoever owns the document, which assigns unique ones through ``note_implicit_target``,
    so two nodes documented on one page cannot collide.
    """
    section = nodes.section(names=[nodes.fully_normalize_name(title)])
    section += nodes.title(title, title)
    section += list(body)
    return section


def build_includes_note(refs: Sequence[str]) -> nodes.note:
    """A note naming the documents this interface is composed from."""
    intro = 'This interface includes:'
    note = nodes.note()
    note += nodes.paragraph(intro, intro)
    note += bullet_list(refs, code_item)
    return note


def build_category_section(category: Category[RowT], rows: Sequence[RowT]) -> nodes.section:
    """One category as a titled section holding its table."""
    return build_section(category.title, [build_table(category.columns, rows)])


def build_node_section(summary: NodeSummary, title: str) -> nodes.section:
    """A whole node interface as one titled section.

    The body is the description, a note on what the document includes, and a subsection per populated category.
    An empty summary is a bare titled section, which is the truthful rendering of a document that declares nothing.
    """
    return build_section(
        title,
        [
            *paragraphs(summary.description),
            *([build_includes_note(summary.includes)] if summary.includes else []),
            *(build_category_section(category, rows) for category in CATEGORIES if (rows := category.rows(summary))),
        ],
    )


# --------------------------------
# Locating the document
# --------------------------------

# Suffixes a NoDL file is written with, stripped from a filename to leave the node's name.
DOCUMENT_SUFFIXES = ('.yaml', '.yml', '.json')


def default_title_for_path(path: Path) -> str:
    """The heading to use for a file the author did not title: its name without NoDL suffixes."""
    name = path.name
    for suffix in DOCUMENT_SUFFIXES:
        name = name.removesuffix(suffix)
    return name.removesuffix('.nodl')


def default_title_for_ref(ref: str) -> str:
    """The heading to use for a reference the author did not title: the reference without its scheme."""
    _, _, remainder = ref.partition('://')
    return remainder or ref


def include_paths(tree: DocumentTree, origin: Path) -> list[Path]:
    """Every file the tree includes, transitively, in traversal order.

    A ``DocumentTree`` keeps the refs it resolved but not the paths it resolved them to,
    so each ref is resolved again against the document that made it.
    Resolution is deterministic, and the tree was built by the same walk, so this recovers the same files.
    """

    def walk(included: IncludedDocument, parent: Path) -> list[Path]:
        path = resolve(included.ref, parent)
        return [path, *(descendant for child in included.resolved_includes for descendant in walk(child, path))]

    return [path for child in tree.resolved_includes for path in walk(child, origin)]


# --------------------------------
# The directive
# --------------------------------


class NodlNodeDirective(SphinxDirective):
    """Render a NoDL document's effective interface.

    The argument is either a path to the document, resolved the way ``literalinclude`` resolves one
    (relative to the containing page, or to the source root when it starts with ``/``),
    or a reference such as ``nodl://<package>/<name>`` resolved through the registered NoDL resolvers,
    which is how a page documents a dependency it does not ship.

    The document is loaded, resolved, and merged, so the rendering is what the node actually exposes.
    """

    has_content = False
    required_arguments = 1
    optional_arguments = 0
    final_argument_whitespace = True
    option_spec = {'title': directives.unchanged_required}

    def run(self) -> list[nodes.Node]:
        reference = self.arguments[0]
        try:
            path, default_title = self._locate(reference)
            # The merged document is discarded: the summary merges the tree itself.
            # Loading through the documented entry point keeps validation identical to the CLI's.
            _, tree = load_nodl_with_doc_tree(path)
            dependencies = [path, *include_paths(tree, path)]
        except Exception as error:
            # Any failure to produce the whole interface fails the build here,
            # rather than leaving a page that silently documents less than the node does.
            raise self.error(f'nodl-node {reference}: {error}') from error

        for dependency in dependencies:
            self.env.note_dependency(dependency)

        section = build_node_section(summarize_tree(tree), self.options.get('title', default_title))
        self.set_source_info(section)
        # Every section produced here, the node section itself included, takes its id from the document,
        # which keeps ids unique across every node documented on this page.
        for produced in section.findall(nodes.section):
            self.state.document.note_implicit_target(produced)
        return [section]

    def _locate(self, reference: str) -> tuple[Path, str]:
        """The file ``reference`` names, and the heading to use when the author gave no title."""
        origin = Path(self.env.doc2path(self.env.docname))
        if resolver_for(reference) is not None:
            return resolve(reference, origin), default_title_for_ref(reference)
        _, absolute = self.env.relfn2path(reference)
        return Path(absolute), default_title_for_path(Path(absolute))
