# -*- coding: utf-8 -*-
"""Tests for the shared test helpers in ``tests/test_utils/helpers.py``."""

import shutil

import pytest

from tests.test_utils.helpers import assert_dict_contains
from tests.test_utils.helpers import create_temp_directory
from tests.test_utils.helpers import create_temp_file


class TestCreateTempFile:
    """Tests for create_temp_file."""

    def test_writes_content_with_default_suffix(self):
        path = create_temp_file("print('hi')\n")
        try:
            assert path.exists()
            assert path.suffix == ".py"
            assert path.read_text(encoding="utf-8") == "print('hi')\n"
        finally:
            path.unlink(missing_ok=True)

    def test_uses_custom_suffix(self):
        path = create_temp_file("x = 1", suffix=".txt")
        try:
            assert path.suffix == ".txt"
            assert path.read_text(encoding="utf-8") == "x = 1"
        finally:
            path.unlink(missing_ok=True)


class TestCreateTempDirectory:
    """Tests for create_temp_directory."""

    def test_creates_unique_existing_directories(self):
        first = create_temp_directory()
        second = create_temp_directory()
        try:
            assert first.is_dir()
            assert second.is_dir()
            assert first != second
        finally:
            shutil.rmtree(first, ignore_errors=True)
            shutil.rmtree(second, ignore_errors=True)


class TestAssertDictContains:
    """Tests for assert_dict_contains."""

    def test_passes_for_subset(self):
        assert_dict_contains({"a": 1}, {"a": 1, "b": 2})

    def test_missing_key_raises(self):
        with pytest.raises(AssertionError, match="not found in superset"):
            assert_dict_contains({"missing": 1}, {"a": 1})

    def test_value_mismatch_raises(self):
        with pytest.raises(AssertionError, match="Value mismatch"):
            assert_dict_contains({"a": 2}, {"a": 1})
