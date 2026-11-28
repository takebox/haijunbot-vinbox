# -*- coding: utf-8 -*-
"""haijunbot_tools.edit_file module unit tests (find-and-replace tool)"""

import os

import pytest

from haijunbot.haijunbot_tools.edit_file import edit_file


class TestEditFile:
    """Tests for edit_file class (find and replace)"""

    @pytest.fixture
    def tool(self):
        """Create test edit_file instance"""
        return edit_file()

    @pytest.fixture
    def temp_file(self, tmp_path):
        """Create temporary file"""
        path = tmp_path / "sample.py"
        path.write_text(
            "def hello():\n    print('Hello, World!')\n\ndef add(a, b):\n    return a + b\n",
            encoding="utf-8",
        )
        return str(path)

    def _read(self, path):
        with open(path, encoding="utf-8") as f:
            return f.read()

    def test_unique_match_replace(self, tool, temp_file):
        """Unique match replacement"""
        result = tool.execute(
            {
                "file_path": temp_file,
                "search": "return a + b",
                "replace": "return a - b",
            }
        )
        assert result["success"] is True
        assert "modified successfully" in result["stdout"]
        assert "return a - b" in self._read(temp_file)

    def test_multiple_match_fails_by_default(self, tool, tmp_path):
        """Multiple matches raise error by default"""
        path = tmp_path / "multi.txt"
        path.write_text("x\nx\n", encoding="utf-8")
        result = tool.execute({"file_path": str(path), "search": "x", "replace": "y"})
        assert result["success"] is False
        assert "matched 2 places" in result["stderr"]
        assert path.read_text(encoding="utf-8") == "x\nx\n"

    def test_replace_all(self, tool, tmp_path):
        """replace_all=true replaces all"""
        path = tmp_path / "multi.txt"
        path.write_text("x\nx\n", encoding="utf-8")
        result = tool.execute(
            {
                "file_path": str(path),
                "search": "x",
                "replace": "y",
                "replace_all": True,
            }
        )
        assert result["success"] is True
        assert path.read_text(encoding="utf-8") == "y\ny\n"

    def test_not_found(self, tool, temp_file):
        """Error when text not found"""
        result = tool.execute(
            {"file_path": temp_file, "search": "nonexistent_text", "replace": "x"}
        )
        assert result["success"] is False
        assert "No matching text was found" in result["stderr"]

    def test_search_equals_replace(self, tool, temp_file):
        """search == replace is treated as invalid operation"""
        result = tool.execute(
            {
                "file_path": temp_file,
                "search": "return a + b",
                "replace": "return a + b",
            }
        )
        assert result["success"] is False
        assert "invalid operation" in result["stderr"].lower()

    def test_empty_search_rejected(self, tool, temp_file):
        """Empty search is rejected with hint to use write_file"""
        result = tool.execute(
            {"file_path": temp_file, "search": "", "replace": "whole new content"}
        )
        assert result["success"] is False
        assert "write_file" in result["stderr"]

    def test_delete_by_empty_replace(self, tool, tmp_path):
        """replace="" deletes matched text"""
        path = tmp_path / "del.txt"
        path.write_text("keep\ndel\n", encoding="utf-8")
        result = tool.execute(
            {"file_path": str(path), "search": "del\n", "replace": ""}
        )
        assert result["success"] is True
        assert path.read_text(encoding="utf-8") == "keep\n"

    def test_quote_normalization_match(self, tool, tmp_path):
        """Straight-quote search can match curly-quote file, and preserves curly-quote style"""
        path = tmp_path / "quote.txt"
        path.write_text("s = \u201chello\u201d\n", encoding="utf-8")
        result = tool.execute(
            {"file_path": str(path), "search": 's = "hello"', "replace": 's = "world"'}
        )
        assert result["success"] is True
        assert path.read_text(encoding="utf-8") == "s = \u201cworld\u201d\n"

    def test_missing_search(self, tool, temp_file):
        """Missing search raises error"""
        result = tool.execute({"file_path": temp_file, "replace": "x"})
        assert result["success"] is False
        assert "search" in result["stderr"]

    def test_missing_replace(self, tool, temp_file):
        """Missing replace raises error"""
        result = tool.execute({"file_path": temp_file, "search": "x"})
        assert result["success"] is False
        assert "replace" in result["stderr"]

    def test_replace_all_wrong_type(self, tool, temp_file):
        """replace_all with non-boolean type raises error"""
        result = tool.execute(
            {
                "file_path": temp_file,
                "search": "x",
                "replace": "y",
                "replace_all": "yes",
            }
        )
        assert result["success"] is False
        assert "replace_all" in result["stderr"]

    def test_no_backup_left(self, tool, temp_file):
        """No backup file remains after success"""
        tool.execute(
            {
                "file_path": temp_file,
                "search": "return a + b",
                "replace": "return a - b",
            }
        )
        assert not os.path.exists(temp_file + ".bak")

    def test_name_matches_module(self):
        """Tool name matches module name (registry loading convention)"""
        assert edit_file.name == "edit_file"
