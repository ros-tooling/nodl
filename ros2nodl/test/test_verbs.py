"""Unit tests for ros2nodl verb implementations."""

from __future__ import annotations

import argparse
import io
import sys
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# ValidateVerb
# ---------------------------------------------------------------------------

class TestValidateVerb:

    def setup_method(self):
        from ros2nodl.verb.validate import ValidateVerb
        self.verb = ValidateVerb()

    def _make_args(self, file=None, format=None):
        args = argparse.Namespace()
        args.file = file
        args.format = format
        return args

    def test_valid_yaml_file(self, tmp_path):
        nodl_file = tmp_path / 'valid.yaml'
        nodl_file.write_text('publishers:\n  - topic: /t\n    type: std_msgs/msg/String\n')
        args = self._make_args(file=str(nodl_file))
        result = self.verb.main(args=args)
        assert result == 0

    def test_valid_json_file(self, tmp_path):
        nodl_file = tmp_path / 'valid.json'
        nodl_file.write_text('{"publishers": [{"topic": "/t", "type": "std_msgs/msg/String"}]}')
        args = self._make_args(file=str(nodl_file), format='json')
        result = self.verb.main(args=args)
        assert result == 0

    def test_invalid_file_returns_1(self, tmp_path, capsys):
        nodl_file = tmp_path / 'bad.yaml'
        nodl_file.write_text('parameters:\n  p:\n    type: not_a_real_type\n')
        args = self._make_args(file=str(nodl_file))
        result = self.verb.main(args=args)
        assert result == 1
        captured = capsys.readouterr()
        assert 'Validation error' in captured.err

    def test_valid_from_stdin(self, monkeypatch):
        stdin_content = 'publishers:\n  - topic: /t\n    type: std_msgs/msg/String\n'
        monkeypatch.setattr('sys.stdin', io.StringIO(stdin_content))
        args = self._make_args(file=None)
        result = self.verb.main(args=args)
        assert result == 0

    def test_empty_document_is_valid(self, tmp_path):
        nodl_file = tmp_path / 'empty.yaml'
        nodl_file.write_text('{}\n')
        args = self._make_args(file=str(nodl_file))
        result = self.verb.main(args=args)
        assert result == 0

    def test_nonexistent_file_returns_1(self, capsys):
        args = self._make_args(file='/nonexistent/path/file.yaml')
        result = self.verb.main(args=args)
        assert result == 1
        captured = capsys.readouterr()
        assert 'Error' in captured.err

    def test_success_prints_message(self, tmp_path, capsys):
        nodl_file = tmp_path / 'ok.yaml'
        nodl_file.write_text('{}\n')
        args = self._make_args(file=str(nodl_file))
        self.verb.main(args=args)
        captured = capsys.readouterr()
        assert 'Valid' in captured.out


# ---------------------------------------------------------------------------
# DescribeVerb
# ---------------------------------------------------------------------------

class TestDescribeVerb:

    def setup_method(self):
        from ros2nodl.verb.describe import DescribeVerb
        self.verb = DescribeVerb()

    def _make_args(self, node_name='/test_node', format='yaml',
                   assume_current_as_default=False, discovery_timeout=0.5):
        args = argparse.Namespace()
        args.node_name = node_name
        args.format = format
        args.assume_current_as_default = assume_current_as_default
        args.discovery_timeout = discovery_timeout
        return args

    def test_node_not_found_returns_1(self, capsys):
        with patch('nodl.describe.describe') as mock_describe:
            mock_describe.side_effect = RuntimeError('not found')
            args = self._make_args()
            result = self.verb.main(args=args)
        assert result == 1
        captured = capsys.readouterr()
        assert 'Error' in captured.err

    def test_yaml_output(self, capsys):
        mock_node_msg = MagicMock()
        mock_node_msg.name = '/test_node'
        mock_node_msg.parameters = []
        mock_node_msg.parameter_values = []
        mock_node_msg.publishers = []
        mock_node_msg.subscriptions = []
        mock_node_msg.service_servers = []
        mock_node_msg.service_clients = []
        mock_node_msg.action_servers = []
        mock_node_msg.action_clients = []

        with patch('nodl.describe.describe', return_value=mock_node_msg):
            args = self._make_args(format='yaml')
            result = self.verb.main(args=args)

        assert result == 0
        captured = capsys.readouterr()
        assert 'node' in captured.out

    def test_json_output(self, capsys):
        mock_node_msg = MagicMock()
        mock_node_msg.name = '/test_node'
        mock_node_msg.parameters = []
        mock_node_msg.parameter_values = []
        mock_node_msg.publishers = []
        mock_node_msg.subscriptions = []
        mock_node_msg.service_servers = []
        mock_node_msg.service_clients = []
        mock_node_msg.action_servers = []
        mock_node_msg.action_clients = []

        with patch('nodl.describe.describe', return_value=mock_node_msg):
            args = self._make_args(format='json')
            result = self.verb.main(args=args)

        assert result == 0
        import json
        captured = capsys.readouterr()
        parsed = json.loads(captured.out)
        assert 'node' in parsed

    def test_discovery_timeout_passed(self):
        mock_node_msg = MagicMock()
        mock_node_msg.name = '/test_node'
        mock_node_msg.parameters = []
        mock_node_msg.parameter_values = []
        mock_node_msg.publishers = []
        mock_node_msg.subscriptions = []
        mock_node_msg.service_servers = []
        mock_node_msg.service_clients = []
        mock_node_msg.action_servers = []
        mock_node_msg.action_clients = []

        with patch('nodl.describe.describe', return_value=mock_node_msg) as mock_desc:
            args = self._make_args(discovery_timeout=3.7)
            self.verb.main(args=args)
            mock_desc.assert_called_once_with('/test_node', discovery_timeout_sec=3.7)
