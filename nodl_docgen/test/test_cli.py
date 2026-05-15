"""Tests for the nodl_docgen CLI script."""
import importlib.machinery
import importlib.util
import sys
from pathlib import Path

import pytest

# Load the CLI script (no .py extension) as a module.
_SCRIPT = Path(__file__).parents[1] / 'scripts' / 'nodl_docgen'
_loader = importlib.machinery.SourceFileLoader('nodl_docgen_cli', str(_SCRIPT))
_spec = importlib.util.spec_from_loader('nodl_docgen_cli', _loader)
_cli = importlib.util.module_from_spec(_spec)
_loader.exec_module(_cli)


_NODL_YAML = """\
nodl_version: "1"
node:
  name: test_node
parameters:
  rate:
    type: double
    default_value: 10.0
    description: Publish rate
publishers:
  - topic: /out
    type: std_msgs/msg/String
"""


def test_cli_creates_output_file(tmp_path):
    nodl_file = tmp_path / 'test_node.nodl.yaml'
    nodl_file.write_text(_NODL_YAML)
    out_file = tmp_path / 'out' / 'test_node.rst'

    sys.argv = [
        'nodl_docgen',
        '--nodl-file', str(nodl_file),
        '--output', str(out_file),
    ]
    _cli.main()

    assert out_file.exists()


def test_cli_output_contains_node_name(tmp_path):
    nodl_file = tmp_path / 'test_node.nodl.yaml'
    nodl_file.write_text(_NODL_YAML)
    out_file = tmp_path / 'test_node.rst'

    sys.argv = [
        'nodl_docgen',
        '--nodl-file', str(nodl_file),
        '--output', str(out_file),
    ]
    _cli.main()

    rst = out_file.read_text()
    assert 'test_node' in rst
    assert '.. list-table::' in rst


def test_cli_creates_parent_directories(tmp_path):
    nodl_file = tmp_path / 'test_node.nodl.yaml'
    nodl_file.write_text(_NODL_YAML)
    out_file = tmp_path / 'a' / 'b' / 'c' / 'test_node.rst'

    sys.argv = [
        'nodl_docgen',
        '--nodl-file', str(nodl_file),
        '--output', str(out_file),
    ]
    _cli.main()

    assert out_file.exists()
