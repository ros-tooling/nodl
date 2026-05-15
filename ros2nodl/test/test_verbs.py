"""Unit tests for ros2nodl verb implementations."""

from __future__ import annotations

import argparse
import io


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

