"""Tests for the Sphinx extension."""
import pytest

sphinx = pytest.importorskip('sphinx')

from pathlib import Path
from unittest.mock import MagicMock, patch

from docutils import nodes
from docutils.parsers.rst import Parser
from docutils.frontend import OptionParser
from docutils.utils import new_document

from nodl_docgen import sphinx_ext


_NODL_YAML = """\
nodl_version: "1"
node:
  name: ext_test_node
publishers:
  - topic: /out
    type: std_msgs/msg/String
"""


def _make_directive_mock(nodl_path: str, src_file: Path):
    """Return a minimally-mocked NodlDirective instance."""
    directive = MagicMock(spec=sphinx_ext.NodlDirective)
    directive.arguments = [nodl_path]
    directive.content_offset = 0
    directive.lineno = 1
    directive.reporter = MagicMock()
    directive.reporter.error.return_value = nodes.system_message()
    directive.env = MagicMock()
    directive.env.docdir = str(src_file.parent)
    directive.get_source_info.return_value = (str(src_file), 1)
    directive.state = MagicMock()

    # Capture nested_parse output by actually running the RST through docutils.
    def fake_nested_parse(string_list, offset, container):
        parser = Parser()
        settings = OptionParser(components=(Parser,)).get_default_values()
        doc = new_document('<test>', settings)
        parser.parse('\n'.join(string_list), doc)
        container.children.extend(doc.children)

    directive.state.nested_parse.side_effect = fake_nested_parse
    return directive


def test_directive_produces_nodes(tmp_path):
    nodl_file = tmp_path / 'ext_test_node.nodl.yaml'
    nodl_file.write_text(_NODL_YAML)
    fake_src = tmp_path / 'index.rst'

    directive = _make_directive_mock(nodl_file.name, fake_src)
    result = sphinx_ext.NodlDirective.run(directive)

    assert len(result) > 0
    assert any(isinstance(n, nodes.section) or isinstance(n, nodes.title) for n in result)


def test_directive_missing_file_returns_error(tmp_path):
    fake_src = tmp_path / 'index.rst'
    directive = _make_directive_mock('nonexistent.nodl.yaml', fake_src)

    result = sphinx_ext.NodlDirective.run(directive)

    directive.reporter.error.assert_called_once()


def test_directive_registers_dependency(tmp_path):
    nodl_file = tmp_path / 'ext_test_node.nodl.yaml'
    nodl_file.write_text(_NODL_YAML)
    fake_src = tmp_path / 'index.rst'

    directive = _make_directive_mock(nodl_file.name, fake_src)
    sphinx_ext.NodlDirective.run(directive)

    directive.env.note_dependency.assert_called_once()


def test_setup_registers_directive():
    app = MagicMock()
    result = sphinx_ext.setup(app)

    app.add_directive.assert_called_once_with('nodl', sphinx_ext.NodlDirective)
    assert 'version' in result
    assert result['parallel_read_safe'] is True
