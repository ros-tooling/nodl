"""Unit tests for the ros2nodl validate verb."""

import argparse
import io

from ros2nodl.verb.validate import ValidateVerb


def _make_args(files=None):
    args = argparse.Namespace()
    args.files = files or []
    return args


class TestValidateVerb:

    def setup_method(self):
        self.verb = ValidateVerb()

    def test_valid_yaml_file(self, tmp_path):
        nodl_file = tmp_path / "valid.yaml"
        nodl_file.write_text(
            "nodl_version: 2\n"
            "publishers:\n"
            "  - name: /t\n"
            "    type: std_msgs/msg/String\n"
            "    qos:\n"
            "      history: SYSTEM_DEFAULT\n"
            "      reliability: SYSTEM_DEFAULT\n"
        )
        result = self.verb.main(args=_make_args(files=[str(nodl_file)]))
        assert result == 0

    def test_valid_json_file(self, tmp_path):
        nodl_file = tmp_path / "valid.json"
        nodl_file.write_text(
            '{"nodl_version": 2, "publishers": ['
            '{"name": "/t", "type": "std_msgs/msg/String",'
            ' "qos": {"history": "SYSTEM_DEFAULT", "reliability": "SYSTEM_DEFAULT"}}]}'
        )
        result = self.verb.main(args=_make_args(files=[str(nodl_file)]))
        assert result == 0

    def test_invalid_file_returns_1(self, tmp_path, capsys):
        nodl_file = tmp_path / "bad.yaml"
        nodl_file.write_text("nodl_version: 2\nparameters:\n  p:\n    type: not_a_real_type\n")
        result = self.verb.main(args=_make_args(files=[str(nodl_file)]))
        assert result == 1
        assert "INVALID" in capsys.readouterr().err

    def test_valid_from_stdin(self, monkeypatch):
        monkeypatch.setattr("sys.stdin", io.StringIO("nodl_version: 2\n"))
        result = self.verb.main(args=_make_args())
        assert result == 0

    def test_minimal_document_is_valid(self, tmp_path):
        nodl_file = tmp_path / "min.yaml"
        nodl_file.write_text("nodl_version: 2\n")
        result = self.verb.main(args=_make_args(files=[str(nodl_file)]))
        assert result == 0

    def test_nonexistent_file_returns_1(self, capsys):
        result = self.verb.main(args=_make_args(files=["/nonexistent/path/file.yaml"]))
        assert result == 1
        assert "No such file" in capsys.readouterr().err

    def test_success_prints_ok(self, tmp_path, capsys):
        nodl_file = tmp_path / "ok.yaml"
        nodl_file.write_text("nodl_version: 2\n")
        self.verb.main(args=_make_args(files=[str(nodl_file)]))
        assert "ok" in capsys.readouterr().out

    def test_multiple_files_all_valid(self, tmp_path):
        a = tmp_path / "a.yaml"
        b = tmp_path / "b.yaml"
        a.write_text("nodl_version: 2\n")
        b.write_text("nodl_version: 2\n")
        result = self.verb.main(args=_make_args(files=[str(a), str(b)]))
        assert result == 0

    def test_multiple_files_one_invalid_returns_1(self, tmp_path):
        good = tmp_path / "good.yaml"
        bad = tmp_path / "bad.yaml"
        good.write_text("nodl_version: 2\n")
        bad.write_text("nodl_version: 1\n")
        result = self.verb.main(args=_make_args(files=[str(good), str(bad)]))
        assert result == 1
