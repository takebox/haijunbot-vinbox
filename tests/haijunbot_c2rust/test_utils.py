# -*- coding: utf-8 -*-
"""haijunbot_c2rust.utils module unit tests"""

import json
from pathlib import Path


from haijunbot.haijunbot_c2rust.utils import (
    default_crate_dir,
    dir_tree,
    extract_json_from_summary,
    iter_order_steps,
    read_json,
    write_json,
)


class TestIterOrderSteps:
    """Test iter_order_steps function"""

    def test_empty_file(self, tmp_path):
        """Test empty file"""
        order_file = tmp_path / "order.jsonl"
        order_file.write_text("")
        result = iter_order_steps(order_file)
        assert result == []

    def test_new_format_with_ids(self, tmp_path):
        """Test new format (with ids)"""
        order_file = tmp_path / "order.jsonl"
        order_file.write_text('{"ids": [1, 2, 3]}\n{"ids": [4, 5]}')
        result = iter_order_steps(order_file)
        assert result == [[1, 2, 3], [4, 5]]

    def test_ids_as_strings(self, tmp_path):
        """Test ids as strings"""
        order_file = tmp_path / "order.jsonl"
        order_file.write_text('{"ids": ["1", "2", "3"]}')
        result = iter_order_steps(order_file)
        assert result == [[1, 2, 3]]

    def test_mixed_ids(self, tmp_path):
        """Test mixed format ids"""
        order_file = tmp_path / "order.jsonl"
        order_file.write_text('{"ids": [1, "2", 3]}')
        result = iter_order_steps(order_file)
        assert result == [[1, 2, 3]]

    def test_empty_ids(self, tmp_path):
        """Test empty ids"""
        order_file = tmp_path / "order.jsonl"
        order_file.write_text('{"ids": []}')
        result = iter_order_steps(order_file)
        assert result == []

    def test_invalid_json_line(self, tmp_path):
        """Test invalid JSON line"""
        order_file = tmp_path / "order.jsonl"
        order_file.write_text('{"ids": [1, 2]}\ninvalid json\n{"ids": [3]}')
        result = iter_order_steps(order_file)
        assert result == [[1, 2], [3]]

    def test_no_ids_key(self, tmp_path):
        """Test line without ids key"""
        order_file = tmp_path / "order.jsonl"
        order_file.write_text('{"other": "value"}\n{"ids": [1]}')
        result = iter_order_steps(order_file)
        assert result == [[1]]

    def test_whitespace_lines(self, tmp_path):
        """Test whitespace lines"""
        order_file = tmp_path / "order.jsonl"
        order_file.write_text('\n{"ids": [1]}\n\n{"ids": [2]}\n')
        result = iter_order_steps(order_file)
        assert result == [[1], [2]]


class TestDirTree:
    """Test dir_tree function"""

    def test_empty_directory(self, tmp_path):
        """Test empty directory"""
        result = dir_tree(tmp_path)
        assert result == ""

    def test_simple_structure(self, tmp_path):
        """Test simple directory structure"""
        (tmp_path / "file1.txt").write_text("content")
        (tmp_path / "subdir").mkdir()
        (tmp_path / "subdir" / "file2.txt").write_text("content")
        result = dir_tree(tmp_path)
        assert "- file1.txt" in result
        assert "- subdir/" in result
        assert "  - file2.txt" in result

    def test_excludes_git(self, tmp_path):
        """Test excludes .git directory"""
        (tmp_path / ".git").mkdir()
        (tmp_path / ".git" / "config").write_text("content")
        (tmp_path / "file.txt").write_text("content")
        result = dir_tree(tmp_path)
        assert ".git" not in result
        assert "file.txt" in result

    def test_excludes_target(self, tmp_path):
        """Test excludes target directory"""
        (tmp_path / "target").mkdir()
        (tmp_path / "target" / "file.txt").write_text("content")
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "lib.rs").write_text("content")
        result = dir_tree(tmp_path)
        assert "target" not in result
        assert "src" in result

    def test_excludes_haijunbot(self, tmp_path):
        """Test excludes .haijunbot directory"""
        (tmp_path / ".haijunbot").mkdir()
        (tmp_path / ".haijunbot" / "config.json").write_text("content")
        (tmp_path / "file.txt").write_text("content")
        result = dir_tree(tmp_path)
        assert ".haijunbot" not in result
        assert "file.txt" in result

    def test_nonexistent_directory(self):
        """Test nonexistent directory"""
        result = dir_tree(Path("/nonexistent/path"))
        assert result == ""


class TestDefaultCrateDir:
    """Test default_crate_dir function"""

    def test_current_directory(self, tmp_path, monkeypatch):
        """Test current directory as project root"""
        monkeypatch.chdir(tmp_path)
        result = default_crate_dir(tmp_path)
        expected = tmp_path.parent / f"{tmp_path.name}_rs"
        assert result == expected

    def test_different_directory(self, tmp_path):
        """Test different directory"""
        project_root = tmp_path / "project"
        project_root.mkdir()
        result = default_crate_dir(project_root)
        assert result == project_root

    def test_exception_handling(self, monkeypatch):
        """Test exception handling"""

        def mock_resolve():
            raise OSError("Cannot resolve")

        monkeypatch.setattr(Path, "resolve", lambda self: mock_resolve())
        project_root = Path("test")
        result = default_crate_dir(project_root)
        assert result == project_root


class TestReadJson:
    """Test read_json function"""

    def test_existing_file(self, tmp_path):
        """Test existing file"""
        json_file = tmp_path / "test.json"
        json_file.write_text('{"key": "value"}')
        result = read_json(json_file, {})
        assert result == {"key": "value"}

    def test_nonexistent_file(self, tmp_path):
        """Test nonexistent file"""
        json_file = tmp_path / "nonexistent.json"
        result = read_json(json_file, {"default": "value"})
        assert result == {"default": "value"}

    def test_invalid_json(self, tmp_path):
        """Test invalid JSON"""
        json_file = tmp_path / "invalid.json"
        json_file.write_text("invalid json content")
        result = read_json(json_file, {"default": "value"})
        assert result == {"default": "value"}

    def test_empty_file(self, tmp_path):
        """Test empty file"""
        json_file = tmp_path / "empty.json"
        json_file.write_text("")
        result = read_json(json_file, {"default": "value"})
        assert result == {"default": "value"}


class TestWriteJson:
    """Test write_json function"""

    def test_write_simple_object(self, tmp_path):
        """Test write simple object"""
        json_file = tmp_path / "test.json"
        data = {"key": "value", "number": 42}
        write_json(json_file, data)
        assert json_file.exists()
        result = json.loads(json_file.read_text())
        assert result == data

    def test_write_nested_object(self, tmp_path):
        """Test write nested object"""
        json_file = tmp_path / "test.json"
        data = {"nested": {"key": "value"}, "list": [1, 2, 3]}
        write_json(json_file, data)
        result = json.loads(json_file.read_text())
        assert result == data

    def test_create_parent_directories(self, tmp_path):
        """Test create parent directories"""
        json_file = tmp_path / "subdir" / "test.json"
        data = {"key": "value"}
        write_json(json_file, data)
        assert json_file.exists()
        result = json.loads(json_file.read_text())
        assert result == data

    def test_unicode_content(self, tmp_path):
        """Test Unicode content"""
        json_file = tmp_path / "test.json"
        data = {"chinese": "test", "emoji": "\U0001f680"}
        write_json(json_file, data)
        result = json.loads(json_file.read_text(encoding="utf-8"))
        assert result == data


class TestExtractJsonFromSummary:
    """Test extract_json_from_summary function"""

    def test_valid_summary_block(self):
        """Test valid SUMMARY block"""
        text = '<SUMMARY>{"key": "value"}</SUMMARY>'
        result, error = extract_json_from_summary(text)
        assert error is None
        assert result == {"key": "value"}

    def test_summary_with_whitespace(self):
        """Test SUMMARY block with whitespace"""
        text = '<SUMMARY>\n{"key": "value"}\n</SUMMARY>'
        result, error = extract_json_from_summary(text)
        assert error is None
        assert result == {"key": "value"}

    def test_summary_with_trailing_comma(self):
        """Test JSON with trailing comma (jsonnet compatible)"""
        text = '<SUMMARY>{"key": "value",}</SUMMARY>'
        result, error = extract_json_from_summary(text)
        # jsonnet should handle trailing commas
        assert error is None or result == {"key": "value"}

    def test_no_summary_tags(self):
        """Test without SUMMARY tags"""
        text = '{"key": "value"}'
        result, error = extract_json_from_summary(text)
        assert error is None
        assert result == {"key": "value"}

    def test_empty_summary_block(self):
        """Test empty SUMMARY block"""
        text = "<SUMMARY></SUMMARY>"
        result, error = extract_json_from_summary(text)
        assert error is not None
        assert result == {}

    def test_invalid_json(self):
        """Test invalid JSON"""
        text = "<SUMMARY>{invalid json}</SUMMARY>"
        result, error = extract_json_from_summary(text)
        assert error is not None
        assert result == {}

    def test_non_dict_result(self):
        """Test non-dict result"""
        text = '<SUMMARY>["array"]</SUMMARY>'
        result, error = extract_json_from_summary(text)
        assert error is not None
        assert result == {}

    def test_empty_string(self):
        """Test empty string"""
        result, error = extract_json_from_summary("")
        assert error is not None
        assert result == {}

    def test_none_input(self):
        """Test None input"""
        result, error = extract_json_from_summary(None)
        assert error is not None
        assert result == {}

    def test_case_insensitive_tags(self):
        """Test case-insensitive tags"""
        text = '<summary>{"key": "value"}</summary>'
        result, error = extract_json_from_summary(text)
        assert error is None
        assert result == {"key": "value"}
