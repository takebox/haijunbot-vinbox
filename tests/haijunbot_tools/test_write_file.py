# -*- coding: utf-8 -*-
"""Unit tests for haijunbot_tools.write_file module"""

import os

import pytest

from haijunbot.haijunbot_tools.write_file import write_file


class TestWriteFile:
    """Tests for write_file class"""

    @pytest.fixture
    def tool(self):
        """Create test write_file instance"""
        return write_file()

    @pytest.fixture
    def temp_file(self, tmp_path):
        """Create temporary file"""
        path = tmp_path / "sample.py"
        path.write_text("def hello():\n    print('hi')\n", encoding="utf-8")
        return str(path)

    def test_overwrite_existing_file(self, tool, temp_file):
        """Overwrite existing file"""
        result = tool.execute({"file_path": temp_file, "content": "new content\n"})
        assert result["success"] is True
        assert result["stderr"] == ""
        with open(temp_file, encoding="utf-8") as f:
            assert f.read() == "new content\n"

    def test_create_new_file_with_parent_dirs(self, tool, tmp_path):
        """Create when file does not exist (including parent directories)"""
        path = tmp_path / "a" / "b" / "new.txt"
        result = tool.execute({"file_path": str(path), "content": "hello"})
        assert result["success"] is True
        assert path.read_text(encoding="utf-8") == "hello"

    def test_empty_content_clears_file(self, tool, temp_file):
        """Empty content clears the file"""
        result = tool.execute({"file_path": temp_file, "content": ""})
        assert result["success"] is True
        with open(temp_file, encoding="utf-8") as f:
            assert f.read() == ""

    def test_encoding_preserved(self, tool, tmp_path):
        """Preserve original file encoding (utf-8)"""
        path = tmp_path / "enc.txt"
        path.write_text("Chinese content\n", encoding="utf-8")
        result = tool.execute({"file_path": str(path), "content": "New Chinese\n"})
        assert result["success"] is True
        assert "utf-8" in result["stdout"]
        assert path.read_text(encoding="utf-8") == "New Chinese\n"

    def test_no_backup_left(self, tool, temp_file):
        """No backup file remains after successful write"""
        tool.execute({"file_path": temp_file, "content": "x\n"})
        assert not os.path.exists(temp_file + ".bak")

    def test_missing_file_path(self, tool):
        """Missing file_path raises error"""
        result = tool.execute({"content": "x"})
        assert result["success"] is False
        assert "file_path" in result["stderr"]

    def test_missing_content(self, tool, temp_file):
        """Missing content raises error"""
        result = tool.execute({"file_path": temp_file})
        assert result["success"] is False
        assert "content" in result["stderr"]

    def test_content_wrong_type(self, tool, temp_file):
        """content with wrong type raises error"""
        result = tool.execute({"file_path": temp_file, "content": 123})
        assert result["success"] is False
        assert "content" in result["stderr"]

    def test_file_path_wrong_type(self, tool):
        """file_path with wrong type raises error"""
        result = tool.execute({"file_path": 123, "content": "x"})
        assert result["success"] is False
        assert "file_path" in result["stderr"]

    def test_name_matches_module(self):
        """Tool name matches module name (registry loading convention)"""
        assert write_file.name == "write_file"
