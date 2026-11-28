# -*- coding: utf-8 -*-
"""haijunbot_tools.edit_file_by_line module unit tests"""

import os

import pytest

from haijunbot.haijunbot_tools.edit_file_by_line import edit_file_by_line


class TestEditFileByLine:
    """Tests for edit_file_by_line class"""

    @pytest.fixture
    def tool(self):
        """Create test edit_file_by_line instance"""
        return edit_file_by_line()

    @pytest.fixture
    def temp_file(self, tmp_path):
        """Create temporary file with 5 lines"""
        path = tmp_path / "sample.txt"
        path.write_text("l1\nl2\nl3\nl4\nl5\n", encoding="utf-8")
        return str(path)

    def _read(self, path):
        with open(path, encoding="utf-8") as f:
            return f.read()

    def test_replace_single_line(self, tool, temp_file):
        """Single line replacement"""
        result = tool.execute(
            {"file_path": temp_file, "start_line": 2, "end_line": 2, "content": "X"}
        )
        assert result["success"] is True
        assert "modified successfully" in result["stdout"]
        assert self._read(temp_file) == "l1\nX\nl3\nl4\nl5\n"

    def test_replace_multiple_lines(self, tool, temp_file):
        """Multiple line range replacement (inclusive)"""
        result = tool.execute(
            {
                "file_path": temp_file,
                "start_line": 2,
                "end_line": 4,
                "content": "X\nY",
            }
        )
        assert result["success"] is True
        assert self._read(temp_file) == "l1\nX\nY\nl5\n"

    def test_replace_last_line(self, tool, temp_file):
        """Replace last line (no extra newline added)"""
        result = tool.execute(
            {"file_path": temp_file, "start_line": 5, "end_line": 5, "content": "Z"}
        )
        assert result["success"] is True
        assert self._read(temp_file) == "l1\nl2\nl3\nl4\nZ"

    def test_delete_range(self, tool, temp_file):
        """Delete range (content=""): original range content cleared, empty line placeholder retained"""
        result = tool.execute(
            {"file_path": temp_file, "start_line": 2, "end_line": 3, "content": ""}
        )
        assert result["success"] is True
        assert self._read(temp_file) == "l1\n\nl4\nl5\n"

    def test_start_line_out_of_range(self, tool, temp_file):
        """start_line exceeding total line count raises error"""
        result = tool.execute(
            {"file_path": temp_file, "start_line": 99, "end_line": 100, "content": "x"}
        )
        assert result["success"] is False
        assert "exceeds the total number of lines" in result["stderr"]
        assert self._read(temp_file) == "l1\nl2\nl3\nl4\nl5\n"

    def test_start_line_less_than_one(self, tool, temp_file):
        """start_line < 1 raises error"""
        result = tool.execute(
            {"file_path": temp_file, "start_line": 0, "end_line": 1, "content": "x"}
        )
        assert result["success"] is False
        assert "start_line" in result["stderr"]

    def test_end_line_less_than_start_line(self, tool, temp_file):
        """end_line < start_line raises error"""
        result = tool.execute(
            {"file_path": temp_file, "start_line": 3, "end_line": 1, "content": "x"}
        )
        assert result["success"] is False
        assert "end_line" in result["stderr"]

    def test_non_integer_line(self, tool, temp_file):
        """Non-integer line number raises error"""
        result = tool.execute(
            {"file_path": temp_file, "start_line": "2", "end_line": 3, "content": "x"}
        )
        assert result["success"] is False
        assert "start_line" in result["stderr"]

    def test_missing_content(self, tool, temp_file):
        """Missing content raises error"""
        result = tool.execute({"file_path": temp_file, "start_line": 1, "end_line": 1})
        assert result["success"] is False
        assert "content" in result["stderr"]

    def test_encoding_preserved(self, tool, tmp_path):
        """Preserve original file encoding"""
        path = tmp_path / "enc.txt"
        path.write_text("Chinese line one\nChinese line two\n", encoding="utf-8")
        result = tool.execute(
            {"file_path": str(path), "start_line": 1, "end_line": 1, "content": "Replacement"}
        )
        assert result["success"] is True
        assert "utf-8" in result["stdout"]
        assert path.read_text(encoding="utf-8") == "Replacement\nChinese line two\n"

    def test_no_backup_left(self, tool, temp_file):
        """No backup file remains after success"""
        tool.execute(
            {"file_path": temp_file, "start_line": 1, "end_line": 1, "content": "x"}
        )
        assert not os.path.exists(temp_file + ".bak")

    def test_name_matches_module(self):
        """Tool name matches module name (registry loading convention)"""
        assert edit_file_by_line.name == "edit_file_by_line"
