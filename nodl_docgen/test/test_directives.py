# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Tests for the ``nodl-node`` directive.

Two layers, matching the module under test:
the node builders are exercised directly with a ``NodeSummary``, needing nothing but docutils,
and the directive itself is exercised through a real Sphinx build of a throwaway project.
"""

import logging
from pathlib import Path

import pytest
from docutils import nodes

from nodl_docgen.directives import (
    ACTION_COLUMNS,
    ENDPOINT_COLUMNS,
    PARAMETER_COLUMNS,
    build_node_section,
    build_table,
    default_title_for_path,
    default_title_for_ref,
    include_paths,
)
from nodl_docgen.summarize import ActionRow, EndpointRow, NodeSummary, ParameterRow
from nodl_schema import load_nodl_with_doc_tree

pytest_plugins = ['sphinx.testing.fixtures']


# --------------------------------
# Reading the produced doctree
# --------------------------------


def _titles(node: nodes.Element) -> list[str]:
    """Every section title in document order, the top section's included."""
    return [section[0].astext() for section in node.findall(nodes.section)]


def _tables(node: nodes.Element) -> list[nodes.table]:
    return list(node.findall(nodes.table))


def _headers(table: nodes.table) -> list[str]:
    return [entry.astext() for head in table.findall(nodes.thead) for entry in head.findall(nodes.entry)]


def _body_rows(table: nodes.table) -> list[list[str]]:
    return [
        [entry.astext() for entry in row.findall(nodes.entry)]
        for body in table.findall(nodes.tbody)
        for row in body.findall(nodes.row)
    ]


def _section_named(node: nodes.Element, title: str) -> nodes.section:
    matches = [section for section in node.findall(nodes.section) if section[0].astext() == title]
    assert matches, f'no section titled {title!r} in {_titles(node)}'
    return matches[0]


# --------------------------------
# Tables
# --------------------------------


def test_table_shape_matches_its_columns_and_rows():
    rows = (
        EndpointRow(name='/scan', type='sensor_msgs/msg/LaserScan', qos='KEEP_LAST(5)', description='Raw scans.'),
        EndpointRow(name='/map', type='nav_msgs/msg/OccupancyGrid'),
    )
    table = build_table(ENDPOINT_COLUMNS, rows)

    assert _headers(table) == ['Name', 'Type', 'QoS', 'Description']
    assert _body_rows(table) == [
        ['/scan', 'sensor_msgs/msg/LaserScan', 'KEEP_LAST(5)', 'Raw scans.'],
        ['/map', 'nav_msgs/msg/OccupancyGrid', '', ''],
    ]
    assert next(table.findall(nodes.tgroup))['cols'] == 4


def test_a_column_no_row_fills_in_is_dropped():
    # Services rarely state a QoS profile, and a column of empty cells is noise rather than information.
    rows = (EndpointRow(name='~/reset', type='std_srvs/srv/Trigger'),)
    table = build_table(ENDPOINT_COLUMNS, rows)

    assert _headers(table) == ['Name', 'Type']
    assert _body_rows(table) == [['~/reset', 'std_srvs/srv/Trigger']]


def test_name_and_type_columns_stay_even_when_empty():
    table = build_table(ACTION_COLUMNS, (ActionRow(name='', type=''),))
    assert _headers(table) == ['Name', 'Type']


def test_a_parameter_row_reads_its_constraints_in_the_description_cell():
    rows = (
        ParameterRow(
            name='rate',
            type='double',
            default='1.0',
            description='How often to publish.',
            read_only='yes',
            constraints=('must be greater than 0.0', 'must be less than 100.0'),
            additional_constraints='must divide the control period',
        ),
    )
    table = build_table(PARAMETER_COLUMNS, rows)

    assert _headers(table) == ['Name', 'Type', 'Default', 'Read-only', 'Description']
    assert _body_rows(table) == [
        [
            'rate',
            'double',
            '1.0',
            'yes',
            'How often to publish.\n\nmust be greater than 0.0\n\nmust be less than 100.0'
            '\n\nmust divide the control period',
        ]
    ]
    # The constraint sentences are a list rather than run-on prose.
    assert len(list(table.findall(nodes.bullet_list))) == 1


def test_types_and_values_are_rendered_as_code():
    table = build_table(ACTION_COLUMNS, (ActionRow(name='/dock', type='nav2_msgs/action/Dock', description='Dock.'),))
    literals = [literal.astext() for literal in table.findall(nodes.literal)]
    assert literals == ['/dock', 'nav2_msgs/action/Dock']


# --------------------------------
# Sections
# --------------------------------


def test_an_empty_summary_is_a_bare_titled_section():
    section = build_node_section(NodeSummary(), 'my_node')

    assert _titles(section) == ['my_node']
    assert _tables(section) == []


def test_categories_appear_in_a_fixed_order_and_only_when_populated():
    summary = NodeSummary(
        parameters=(ParameterRow(name='rate', type='double'),),
        subscriptions=(EndpointRow(name='/cmd_vel', type='geometry_msgs/msg/Twist'),),
        action_clients=(ActionRow(name='/dock', type='nav2_msgs/action/Dock'),),
    )

    assert _titles(build_node_section(summary, 'my_node')) == [
        'my_node',
        'Parameters',
        'Subscriptions',
        'Action Clients',
    ]


def test_every_category_gets_its_own_subsection():
    endpoint = (EndpointRow(name='/topic', type='std_msgs/msg/String'),)
    action = (ActionRow(name='/action', type='nav2_msgs/action/Dock'),)
    summary = NodeSummary(
        parameters=(ParameterRow(name='rate', type='double'),),
        publishers=endpoint,
        subscriptions=endpoint,
        service_servers=endpoint,
        service_clients=endpoint,
        action_servers=action,
        action_clients=action,
    )

    assert _titles(build_node_section(summary, 'my_node')) == [
        'my_node',
        'Parameters',
        'Publishers',
        'Subscriptions',
        'Service Servers',
        'Service Clients',
        'Action Servers',
        'Action Clients',
    ]


def test_the_description_becomes_one_paragraph_per_block():
    summary = NodeSummary(description='First line.\n\nSecond block.')
    section = build_node_section(summary, 'my_node')

    assert [paragraph.astext() for paragraph in section.findall(nodes.paragraph)] == ['First line.', 'Second block.']


def test_includes_are_noted_only_when_present():
    assert list(build_node_section(NodeSummary(), 'my_node').findall(nodes.note)) == []

    section = build_node_section(NodeSummary(includes=('nodl://sensor_common/imu',)), 'my_node')
    notes = list(section.findall(nodes.note))

    assert len(notes) == 1
    assert 'nodl://sensor_common/imu' in notes[0].astext()


def test_sections_carry_names_but_leave_ids_to_the_document():
    # Ids are assigned by whoever owns the document, so two nodes on one page cannot collide.
    section = build_node_section(NodeSummary(parameters=(ParameterRow(name='rate', type='double'),)), 'My Node')

    assert section['names'] == ['my node']
    assert section['ids'] == []
    assert _section_named(section, 'Parameters')['names'] == ['parameters']


# --------------------------------
# Locating the document
# --------------------------------


@pytest.mark.parametrize(
    ('name', 'expected'),
    [
        ('my_node.nodl.yaml', 'my_node'),
        ('my_node.nodl.yml', 'my_node'),
        ('my_node.nodl.json', 'my_node'),
        ('my_node.yaml', 'my_node'),
        ('my_node', 'my_node'),
    ],
)
def test_the_default_title_of_a_path_is_its_stem(name: str, expected: str):
    assert default_title_for_path(Path('/doc/nodl') / name) == expected


def test_the_default_title_of_a_ref_drops_only_the_scheme():
    assert default_title_for_ref('nodl://sensor_common/imu') == 'sensor_common/imu'
    assert default_title_for_ref('local://shared.nodl.yaml') == 'shared.nodl.yaml'


# --------------------------------
# Build dependencies
# --------------------------------

LEAF = 'nodl_version: 2\n'
MIDDLE = 'nodl_version: 2\ninclude:\n  - ref: local://leaf.nodl.yaml\n'
ROOT = 'nodl_version: 2\ndescription: Root.\ninclude:\n  - ref: local://middle.nodl.yaml\n'


def test_include_paths_recovers_every_file_in_the_tree(tmp_path: Path):
    (tmp_path / 'leaf.nodl.yaml').write_text(LEAF)
    (tmp_path / 'middle.nodl.yaml').write_text(MIDDLE)
    root = tmp_path / 'root.nodl.yaml'
    root.write_text(ROOT)

    _, tree = load_nodl_with_doc_tree(root)

    assert include_paths(tree, root) == [tmp_path / 'middle.nodl.yaml', tmp_path / 'leaf.nodl.yaml']


def test_a_document_with_no_includes_has_no_extra_dependencies(tmp_path: Path):
    root = tmp_path / 'root.nodl.yaml'
    root.write_text(LEAF)

    _, tree = load_nodl_with_doc_tree(root)

    assert include_paths(tree, root) == []


# --------------------------------
# The directive, in a real Sphinx build
# --------------------------------

DOCUMENT = """
nodl_version: 2
description: Watches the world.
parameters:
  rate:
    type: double
    default_value: 2.0
    description: Publish rate.
    validation:
      gt: [0.0]
publishers:
  - name: /scan
    type: sensor_msgs/msg/LaserScan
    qos:
      history: KEEP_LAST
      depth: 5
      reliability: BEST_EFFORT
action_servers:
  - name: /navigate
    type: nav2_msgs/action/NavigateToPose
"""

CONF = """
extensions = {extensions}
exclude_patterns = ['_build']
"""


@pytest.fixture(autouse=True)
def _sphinx_warnings_propagate():
    """Let Sphinx see its own warnings, which the ROS environment otherwise hides.

    ``launch_testing`` registers itself as a pytest plugin, and importing it installs a logger class
    that turns propagation off for every logger created afterwards, Sphinx's included.
    Sphinx counts warnings with a handler on its root ``sphinx`` logger,
    so without propagation a page that failed to render would look like a clean build.
    """
    previous = logging.getLoggerClass()
    logging.setLoggerClass(logging.Logger)
    for name, logger in list(logging.Logger.manager.loggerDict.items()):
        if name.startswith('sphinx.') and isinstance(logger, logging.Logger):
            logger.propagate = True
    yield
    logging.setLoggerClass(previous)


def _project(
    root: Path,
    *,
    body: str,
    suffix: str = '.rst',
    document: str = DOCUMENT,
    extensions: tuple[str, ...] = ('nodl_docgen',),
) -> Path:
    """Write a one-page Sphinx project rooted at ``root`` and return its source directory."""
    source = root / 'source'
    (source / 'nodl').mkdir(parents=True)
    (source / 'nodl' / 'my_node.nodl.yaml').write_text(document)
    (source / 'conf.py').write_text(CONF.format(extensions=list(extensions)))
    (source / f'index{suffix}').write_text(body)
    return source


def _build(make_app, source: Path, root: Path):
    """Build ``source`` with warnings as errors, the way a documentation CI job does."""
    app = make_app('html', srcdir=source, builddir=root / 'build', warningiserror=True, freshenv=True)
    app.build()
    return app


def _build_clean(make_app, source: Path, root: Path):
    """Build ``source`` and insist the build reported nothing, since a warning here is a build failure."""
    app = _build(make_app, source, root)
    assert app.statuscode == 0, app.warning.getvalue()
    return app


RST_PAGE = """
Index
=====

.. nodl-node:: nodl/my_node.nodl.yaml
"""


def test_a_directive_renders_the_document_it_names(make_app, tmp_path: Path):
    app = _build_clean(make_app, _project(tmp_path, body=RST_PAGE), tmp_path)
    doctree = app.env.get_doctree('index')

    assert _titles(doctree) == ['Index', 'my_node', 'Parameters', 'Publishers', 'Action Servers']
    assert 'Watches the world.' in doctree.astext()
    assert _body_rows(_tables(_section_named(doctree, 'Parameters'))[0]) == [
        ['rate', 'double', '2.0', 'Publish rate.\n\nmust be greater than 0.0']
    ]
    assert _body_rows(_tables(_section_named(doctree, 'Publishers'))[0]) == [
        ['/scan', 'sensor_msgs/msg/LaserScan', 'KEEP_LAST(5), BEST_EFFORT']
    ]


def test_a_leading_slash_means_the_source_root(make_app, tmp_path: Path):
    source = _project(tmp_path, body=RST_PAGE)
    (source / 'guide').mkdir()
    (source / 'guide' / 'page.rst').write_text('Page\n====\n\n.. nodl-node:: /nodl/my_node.nodl.yaml\n')
    (source / 'index.rst').write_text('Index\n=====\n\n.. toctree::\n\n   guide/page\n')

    app = _build_clean(make_app, source, tmp_path)

    assert _titles(app.env.get_doctree('guide/page')) == [
        'Page',
        'my_node',
        'Parameters',
        'Publishers',
        'Action Servers',
    ]


def test_the_title_option_overrides_the_default_heading(make_app, tmp_path: Path):
    page = 'Index\n=====\n\n.. nodl-node:: nodl/my_node.nodl.yaml\n   :title: Observer node\n'
    app = _build_clean(make_app, _project(tmp_path, body=page), tmp_path)

    assert _titles(app.env.get_doctree('index'))[1] == 'Observer node'


def test_the_document_and_its_includes_are_build_dependencies(make_app, tmp_path: Path):
    source = _project(tmp_path, body=RST_PAGE, document=ROOT)
    (source / 'nodl' / 'middle.nodl.yaml').write_text(MIDDLE)
    (source / 'nodl' / 'leaf.nodl.yaml').write_text(LEAF)

    app = _build_clean(make_app, source, tmp_path)

    assert app.env.dependencies['index'] >= {
        source / 'nodl' / 'my_node.nodl.yaml',
        source / 'nodl' / 'middle.nodl.yaml',
        source / 'nodl' / 'leaf.nodl.yaml',
    }


def test_two_nodes_on_one_page_do_not_collide(make_app, tmp_path: Path):
    page = (
        'Index\n=====\n\n'
        '.. nodl-node:: nodl/my_node.nodl.yaml\n\n'
        '.. nodl-node:: nodl/my_node.nodl.yaml\n   :title: Second\n'
    )
    app = _build_clean(make_app, _project(tmp_path, body=page), tmp_path)
    doctree = app.env.get_doctree('index')

    identifiers = [section['ids'] for section in doctree.findall(nodes.section)]
    assert all(len(ids) == 1 for ids in identifiers), identifiers
    assert len({ids[0] for ids in identifiers}) == len(identifiers)


@pytest.mark.parametrize(
    ('body', 'document'),
    [
        ('Index\n=====\n\n.. nodl-node:: nodl/missing.nodl.yaml\n', DOCUMENT),
        ('Index\n=====\n\n.. nodl-node:: nodl/my_node.nodl.yaml\n', 'nodl_version: 2\nparameters: 7\n'),
        ('Index\n=====\n\n.. nodl-node:: nodl/my_node.nodl.yaml\n', 'nodl_version: 2\ninclude:\n  - ref: bad://x\n'),
        ('Index\n=====\n\n.. nodl-node:: nodl://absent_package/absent\n', DOCUMENT),
    ],
    ids=['missing-file', 'invalid-document', 'unresolvable-include', 'unknown-index-entry'],
)
def test_a_document_that_cannot_be_rendered_fails_the_build(make_app, tmp_path: Path, body: str, document: str):
    app = _build(make_app, _project(tmp_path, body=body, document=document), tmp_path)
    reported = app.warning.getvalue()

    # Under warnings as errors, this warning is what makes the build report failure.
    assert app.statuscode != 0, reported
    assert 'nodl-node' in reported
    # The report points at the directive, which is on the fourth line of every page above.
    assert 'index.rst:4' in reported


MYST_PAGE = """
# Index

```{nodl-node} nodl/my_node.nodl.yaml
:title: From markdown
```
"""


def test_the_directive_works_from_a_markdown_source(make_app, tmp_path: Path):
    pytest.importorskip('myst_parser', reason='MyST is only needed to prove markdown parity')

    source = _project(tmp_path, body=MYST_PAGE, suffix='.md', extensions=('myst_parser', 'nodl_docgen'))
    app = _build_clean(make_app, source, tmp_path)

    assert _titles(app.env.get_doctree('index')) == [
        'Index',
        'From markdown',
        'Parameters',
        'Publishers',
        'Action Servers',
    ]
