# -*- coding: utf-8 -*-
"""haijunbot_c2rust.library_replacer_utils module unit tests"""

import json
from pathlib import Path


from haijunbot.haijunbot_c2rust.library_replacer_utils import (
    is_entry_function,
    load_additional_notes,
    normalize_disabled_libraries,
    normalize_list,
    normalize_list_lower,
    read_source_snippet,
    resolve_symbols_jsonl_path,
    setup_output_paths,
)


class TestResolveSymbolsJsonlPath:
    """Test resolve_symbols_jsonl_path function"""

    def test_existing_file(self, tmp_path):
        """Test existing file"""
        jsonl_file = tmp_path / "symbols.jsonl"
        jsonl_file.write_text("test")
        result = resolve_symbols_jsonl_path(jsonl_file)
        assert result == jsonl_file

    def test_directory(self, tmp_path):
        """Test directory path"""
        data_dir = tmp_path / ".haijunbot" / "c2rust"
        data_dir.mkdir(parents=True)
        result = resolve_symbols_jsonl_path(tmp_path)
        expected = tmp_path / ".haijunbot" / "c2rust" / "symbols.jsonl"
        assert result == expected

    def test_nonexistent_path(self):
        """Test nonexistent path"""
        result = resolve_symbols_jsonl_path(Path("/nonexistent"))
        expected = Path(".") / ".haijunbot" / "c2rust" / "symbols.jsonl"
        assert result == expected

    def test_non_jsonl_file(self, tmp_path):
        """Test non-.jsonl file"""
        txt_file = tmp_path / "symbols.txt"
        txt_file.write_text("test")
        result = resolve_symbols_jsonl_path(txt_file)
        expected = Path(".") / ".haijunbot" / "c2rust" / "symbols.jsonl"
        assert result == expected

    def test_haijunbot_c2rust_directory(self, tmp_path):
        """Test when already a .haijunbot/c2rust directory"""
        # Create .haijunbot/c2rust directory
        c2rust_dir = tmp_path / ".haijunbot" / "c2rust"
        c2rust_dir.mkdir(parents=True)
        # Create symbols.jsonl file
        symbols_file = c2rust_dir / "symbols.jsonl"
        symbols_file.write_text("test")

        # Test passing .haijunbot/c2rust directory
        result = resolve_symbols_jsonl_path(c2rust_dir)
        expected = c2rust_dir / "symbols.jsonl"
        assert result == expected


class TestSetupOutputPaths:
    """Test setup_output_paths function"""

    def test_default_paths(self, tmp_path):
        """Test default paths"""
        data_dir = tmp_path / ".haijunbot" / "c2rust"
        symbols_path, mapping_path, prune_path, order_path, alias_path = (
            setup_output_paths(data_dir, None, None)
        )
        assert symbols_path == data_dir / "symbols_library_pruned.jsonl"
        assert mapping_path == data_dir / "library_replacements.jsonl"
        assert prune_path == data_dir / "symbols_prune.jsonl"
        assert order_path == data_dir / "translation_order_prune.jsonl"
        assert alias_path == data_dir / "translation_order.jsonl"

    def test_custom_paths(self, tmp_path):
        """Test custom paths"""
        data_dir = tmp_path / ".haijunbot" / "c2rust"
        custom_symbols = tmp_path / "custom_symbols.jsonl"
        custom_mapping = tmp_path / "custom_mapping.jsonl"
        symbols_path, mapping_path, prune_path, order_path, alias_path = (
            setup_output_paths(data_dir, custom_symbols, custom_mapping)
        )
        assert symbols_path == custom_symbols
        assert mapping_path == custom_mapping
        assert prune_path == data_dir / "symbols_prune.jsonl"
        assert order_path == data_dir / "translation_order_prune.jsonl"
        assert alias_path == data_dir / "translation_order.jsonl"


class TestReadSourceSnippet:
    """Test read_source_snippet function"""

    def test_basic_read(self, tmp_path):
        """Test basic read"""
        source_file = tmp_path / "test.c"
        source_file.write_text("line1\nline2\nline3\nline4\nline5")
        rec = {
            "file": str(source_file),
            "start_line": 2,
            "end_line": 4,
        }
        result = read_source_snippet(rec)
        assert result == "line2\nline3\nline4"

    def test_single_line(self, tmp_path):
        """Test single line"""
        source_file = tmp_path / "test.c"
        source_file.write_text("line1\nline2\nline3")
        rec = {
            "file": str(source_file),
            "start_line": 2,
            "end_line": 2,
        }
        result = read_source_snippet(rec)
        assert result == "line2"

    def test_max_lines_limit(self, tmp_path):
        """Test maximum line limit"""
        source_file = tmp_path / "test.c"
        source_file.write_text("\n".join(f"line{i}" for i in range(1, 101)))
        rec = {
            "file": str(source_file),
            "start_line": 1,
            "end_line": 100,
        }
        result = read_source_snippet(rec, max_lines=50)
        assert len(result.split("\n")) == 50

    def test_nonexistent_file(self):
        """Test nonexistent file"""
        rec = {
            "file": "/nonexistent/file.c",
            "start_line": 1,
            "end_line": 10,
        }
        result = read_source_snippet(rec)
        assert result == ""

    def test_empty_file(self, tmp_path):
        """Test empty file"""
        source_file = tmp_path / "empty.c"
        source_file.write_text("")
        rec = {
            "file": str(source_file),
            "start_line": 1,
            "end_line": 1,
        }
        result = read_source_snippet(rec)
        assert result == ""

    def test_invalid_line_numbers(self, tmp_path):
        """Test invalid line numbers"""
        source_file = tmp_path / "test.c"
        source_file.write_text("line1\nline2\nline3")
        rec = {
            "file": str(source_file),
            "start_line": 10,
            "end_line": 5,  # end < start
        }
        result = read_source_snippet(rec)
        # When start_line exceeds file range, start_idx goes out of bounds, returns empty string
        assert result == ""

    def test_missing_file_key(self):
        """Test missing file key"""
        rec = {
            "start_line": 1,
            "end_line": 10,
        }
        result = read_source_snippet(rec)
        assert result == ""


class TestNormalizeDisabledLibraries:
    """Test normalize_disabled_libraries function"""

    def test_normal_list(self):
        """Test normal list"""
        disabled = ["lib1", "lib2", "lib3"]
        norm, display = normalize_disabled_libraries(disabled)
        assert norm == ["lib1", "lib2", "lib3"]
        assert display == "lib1, lib2, lib3"

    def test_with_whitespace(self):
        """Test with whitespace"""
        disabled = [" lib1 ", "  lib2  ", "lib3"]
        norm, display = normalize_disabled_libraries(disabled)
        assert norm == ["lib1", "lib2", "lib3"]
        assert display == "lib1, lib2, lib3"

    def test_case_insensitive(self):
        """Test case-insensitive (convert to lowercase)"""
        disabled = ["LIB1", "Lib2", "lib3"]
        norm, display = normalize_disabled_libraries(disabled)
        assert norm == ["lib1", "lib2", "lib3"]
        assert display == "LIB1, Lib2, lib3"  # display preserves original

    def test_empty_list(self):
        """Test empty list"""
        norm, display = normalize_disabled_libraries([])
        assert norm == []
        assert display == ""

    def test_none_input(self):
        """Test None input"""
        norm, display = normalize_disabled_libraries(None)
        assert norm == []
        assert display == ""

    def test_empty_strings(self):
        """Test with empty strings"""
        disabled = ["lib1", "", "lib2", "  ", "lib3"]
        norm, display = normalize_disabled_libraries(disabled)
        assert norm == ["lib1", "lib2", "lib3"]
        assert display == "lib1, lib2, lib3"


class TestLoadAdditionalNotes:
    """Test load_additional_notes function"""

    def test_existing_config(self, tmp_path):
        """Test existing config file"""
        data_dir = tmp_path / ".haijunbot" / "c2rust"
        data_dir.mkdir(parents=True)
        config_file = data_dir / "config.json"
        config_file.write_text(json.dumps({"additional_notes": "Test notes"}))
        result = load_additional_notes(data_dir)
        assert result == "Test notes"

    def test_nonexistent_config(self, tmp_path):
        """Test nonexistent config file"""
        data_dir = tmp_path / ".haijunbot" / "c2rust"
        data_dir.mkdir(parents=True)
        result = load_additional_notes(data_dir)
        assert result == ""

    def test_empty_notes(self, tmp_path):
        """Test empty additional notes"""
        data_dir = tmp_path / ".haijunbot" / "c2rust"
        data_dir.mkdir(parents=True)
        config_file = data_dir / "config.json"
        config_file.write_text(json.dumps({"additional_notes": ""}))
        result = load_additional_notes(data_dir)
        assert result == ""

    def test_invalid_json(self, tmp_path):
        """Test invalid JSON"""
        data_dir = tmp_path / ".haijunbot" / "c2rust"
        data_dir.mkdir(parents=True)
        config_file = data_dir / "config.json"
        config_file.write_text("invalid json")
        result = load_additional_notes(data_dir)
        assert result == ""


class TestNormalizeList:
    """Test normalize_list function"""

    def test_normal_list(self):
        """Test normal list"""
        result = normalize_list(["a", "b", "c"])
        assert result == ["a", "b", "c"]

    def test_with_duplicates(self):
        """Test with duplicates"""
        result = normalize_list(["a", "b", "a", "c", "b"])
        assert result == ["a", "b", "c"]  # Deduplication

    def test_with_whitespace(self):
        """Test with whitespace"""
        result = normalize_list([" a ", "  b  ", "c"])
        assert result == ["a", "b", "c"]

    def test_empty_list(self):
        """Test empty list"""
        result = normalize_list([])
        assert result == []

    def test_none_input(self):
        """Test None input"""
        result = normalize_list(None)
        assert result == []

    def test_non_list_input(self):
        """Test non-list input"""
        result = normalize_list("not a list")
        assert result == []

    def test_empty_strings(self):
        """Test with empty strings"""
        result = normalize_list(["a", "", "b", "  ", "c"])
        assert result == ["a", "b", "c"]


class TestNormalizeListLower:
    """Test normalize_list_lower function"""

    def test_lowercase_conversion(self):
        """Test lowercase conversion"""
        result = normalize_list_lower(["A", "B", "C"])
        assert result == ["a", "b", "c"]

    def test_mixed_case(self):
        """Test mixed case"""
        result = normalize_list_lower(["Hello", "WORLD", "test"])
        # Convert to lowercase, deduplicate, and sort
        assert result == ["hello", "test", "world"]

    def test_with_duplicates(self):
        """Test with duplicates (convert to lowercase first, then deduplicate and sort)"""
        result = normalize_list_lower(["A", "a", "B", "b"])
        # Convert to lowercase -> ["a", "a", "b", "b"]
        # Then deduplicate and sort -> ["a", "b"]
        assert result == ["a", "b"]


class TestIsEntryFunction:
    """Test is_entry_function function"""

    def test_main_function(self):
        """Test main function"""
        rec = {"name": "main", "qualified_name": "main"}
        assert is_entry_function(rec) is True

    def test_qualified_main(self):
        """Test qualified main function"""
        rec = {"name": "main", "qualified_name": "namespace::main"}
        assert is_entry_function(rec) is True

    def test_non_main_function(self):
        """Test non-main function"""
        rec = {"name": "other_func", "qualified_name": "other_func"}
        assert is_entry_function(rec) is False

    def test_custom_entry_via_env(self, monkeypatch):
        """Test custom entry function via environment variable"""
        monkeypatch.setenv("c2rust_delay_entry_symbols", "custom_entry")
        rec = {"name": "custom_entry", "qualified_name": "custom_entry"}
        assert is_entry_function(rec) is True

    def test_custom_entry_multiple(self, monkeypatch):
        """Test multiple custom entry functions"""
        monkeypatch.setenv("c2rust_delay_entry_symbols", "entry1,entry2")
        rec1 = {"name": "entry1", "qualified_name": "entry1"}
        rec2 = {"name": "entry2", "qualified_name": "entry2"}
        rec3 = {"name": "other", "qualified_name": "other"}
        assert is_entry_function(rec1) is True
        assert is_entry_function(rec2) is True
        assert is_entry_function(rec3) is False

    def test_custom_entry_qualified(self, monkeypatch):
        """Test qualified custom entry function"""
        monkeypatch.setenv("c2rust_delay_entry_symbols", "MyClass::init")
        rec = {"name": "init", "qualified_name": "MyClass::init"}
        assert is_entry_function(rec) is True

    def test_case_insensitive(self, monkeypatch):
        """Test case-insensitive"""
        monkeypatch.setenv("c2rust_delay_entry_symbols", "CUSTOM")
        rec = {"name": "custom", "qualified_name": "custom"}
        assert is_entry_function(rec) is True

    def test_empty_name(self):
        """Test empty name"""
        rec = {"name": "", "qualified_name": ""}
        assert is_entry_function(rec) is False
