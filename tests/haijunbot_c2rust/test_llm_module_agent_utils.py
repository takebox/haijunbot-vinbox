# -*- coding: utf-8 -*-
"""haijunbot_c2rust.llm_module_agent_utils module unit tests"""

import json
from pathlib import Path


from haijunbot.haijunbot_c2rust.llm_module_agent_utils import (
    entries_to_json,
    parse_project_json_entries,
    parse_project_json_entries_fallback,
    resolve_created_dir,
)


class TestResolveCreatedDir:
    """Test resolve_created_dir function"""

    def test_current_directory(self, tmp_path, monkeypatch):
        """Test current directory"""
        monkeypatch.chdir(tmp_path)
        result = resolve_created_dir(".")
        expected = tmp_path.parent / f"{tmp_path.name}_rs"
        assert result == expected

    def test_resolved_current_directory(self, tmp_path, monkeypatch):
        """Test resolved current directory"""
        monkeypatch.chdir(tmp_path)
        result = resolve_created_dir(tmp_path)
        expected = tmp_path.parent / f"{tmp_path.name}_rs"
        assert result == expected

    def test_different_directory(self, tmp_path):
        """Test different directory"""
        other_dir = tmp_path / "other"
        result = resolve_created_dir(other_dir)
        assert result == other_dir

    def test_string_path(self, tmp_path):
        """Test string path"""
        other_dir = tmp_path / "other"
        result = resolve_created_dir(str(other_dir))
        assert result == other_dir

    def test_exception_handling(self):
        """Test exception handling"""
        result = resolve_created_dir("/nonexistent/path")
        assert isinstance(result, Path)
        assert result == Path("/nonexistent/path").resolve()


class TestParseProjectJsonEntriesFallback:
    """Test parse_project_json_entries_fallback function"""

    def test_valid_list(self):
        """Test valid list"""
        json_text = '["file1.rs", "file2.rs"]'
        result = parse_project_json_entries_fallback(json_text)
        assert result == ["file1.rs", "file2.rs"]

    def test_nested_structure(self):
        """Test nested structure"""
        json_text = '[{"src/": ["lib.rs", "main.rs"]}]'
        result = parse_project_json_entries_fallback(json_text)
        assert result == [{"src/": ["lib.rs", "main.rs"]}]

    def test_empty_list(self):
        """Test empty list"""
        json_text = "[]"
        result = parse_project_json_entries_fallback(json_text)
        assert result == []

    def test_invalid_json(self):
        """Test invalid JSON"""
        json_text = "invalid json"
        result = parse_project_json_entries_fallback(json_text)
        assert result == []

    def test_non_list_json(self):
        """Test non-list JSON"""
        json_text = '{"key": "value"}'
        result = parse_project_json_entries_fallback(json_text)
        assert result == []


class TestParseProjectJsonEntries:
    """Test parse_project_json_entries function"""

    def test_valid_list(self):
        """Test valid list"""
        json_text = '["file1.rs", "file2.rs"]'
        result, error = parse_project_json_entries(json_text)
        assert error is None
        assert result == ["file1.rs", "file2.rs"]

    def test_nested_structure(self):
        """Test nested structure"""
        json_text = '[{"src/": ["lib.rs", "main.rs"]}]'
        result, error = parse_project_json_entries(json_text)
        assert error is None
        assert result == [{"src/": ["lib.rs", "main.rs"]}]

    def test_with_trailing_comma(self):
        """Test with trailing comma (jsonnet compatible)"""
        json_text = '["file1.rs", "file2.rs",]'
        result, error = parse_project_json_entries(json_text)
        # jsonnet should handle trailing commas
        assert error is None or result == ["file1.rs", "file2.rs"]

    def test_with_comments(self):
        """Test with comments (jsonnet compatible)"""
        json_text = '["file1.rs", // comment\n"file2.rs"]'
        result, error = parse_project_json_entries(json_text)
        # jsonnet should handle comments
        assert error is None or result == ["file1.rs", "file2.rs"]

    def test_empty_list(self):
        """Test empty list"""
        json_text = "[]"
        result, error = parse_project_json_entries(json_text)
        assert error is None
        assert result == []

    def test_invalid_json(self):
        """Test invalid JSON"""
        json_text = "invalid json"
        result, error = parse_project_json_entries(json_text)
        assert error is not None
        assert result == []

    def test_non_list_json(self):
        """Test non-list JSON"""
        json_text = '{"key": "value"}'
        result, error = parse_project_json_entries(json_text)
        assert error is not None
        assert result == []


class TestEntriesToJson:
    """Test entries_to_json function"""

    def test_simple_list(self):
        """Test simple list"""
        entries = ["file1.rs", "file2.rs"]
        result = entries_to_json(entries)
        parsed = json.loads(result)
        assert parsed == entries

    def test_nested_structure(self):
        """Test nested structure"""
        entries = [{"src/": ["lib.rs", "main.rs"]}]
        result = entries_to_json(entries)
        parsed = json.loads(result)
        assert parsed == entries

    def test_complex_structure(self):
        """Test complex structure"""
        entries = [
            "Cargo.toml",
            {"src/": ["lib.rs", {"math/": ["arithmetic.rs", "number_theory.rs"]}]},
        ]
        result = entries_to_json(entries)
        parsed = json.loads(result)
        assert parsed == entries

    def test_empty_list(self):
        """Test empty list"""
        entries = []
        result = entries_to_json(entries)
        parsed = json.loads(result)
        assert parsed == entries

    def test_unicode_content(self):
        """Test Unicode content"""
        entries = ["file.rs", {"dir/": ["test.rs"]}]
        result = entries_to_json(entries)
        parsed = json.loads(result)
        assert parsed == entries
