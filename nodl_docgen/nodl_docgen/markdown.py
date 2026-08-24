# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Simple markdown renderer for NodeSummary."""

from pathlib import Path

from jinja2 import Template

from nodl_docgen.summarize import NodeSummary


def render_markdown(title: str, summary: NodeSummary) -> str:
    template_path = Path(__file__).parent / 'templates' / 'summary.md.j2'
    with template_path.open('r') as f:
        template = Template(f.read())
    return template.render({
        'title': title,
        'summary': summary,
    })
