# -*- coding: utf-8 -*-
"""Unit tests for the haijunbot_utils.file_processors module"""

import pytest

from haijunbot.haijunbot_utils.file_processors import FileProcessor, TextFileProcessor


class TestFileProcessor:
    """Tests for FileProcessor abstract base class"""

    def test_can_handle_not_implemented(self):
        """Test can_handle method not implemented"""
        with pytest.raises(NotImplementedError):
            FileProcessor.can_handle("test.txt")

    def test_extract_text_not_implemented(self):
        """Test extract_text method not implemented"""
        with pytest.raises(NotImplementedError):
            FileProcessor.extract_text("test.txt")


class TestTextFileProcessor:
    """Tests for TextFileProcessor class"""

    def test_can_handle_text_file(self, temp_dir):
        """Test identifying text files"""
        test_file = temp_dir / "test.txt"
        test_file.write_text("Hello, World!", encoding="utf-8")

        result = TextFileProcessor.can_handle(str(test_file))
        assert result is True

    def test_can_handle_binary_file(self, temp_dir):
        """Test identifying binary files"""
        test_file = temp_dir / "test.bin"
        test_file.write_bytes(b"\x00\x01\x02\x03\x04\x05")

        result = TextFileProcessor.can_handle(str(test_file))
        assert result is False

    def test_can_handle_nonexistent_file(self):
        """Test nonexistent file"""
        result = TextFileProcessor.can_handle("/nonexistent/file.txt")
        assert result is False

    def test_extract_text_basic(self, temp_dir):
        """Test extracting basic text"""
        test_file = temp_dir / "test.txt"
        content = "Hello, World!"
        test_file.write_text(content, encoding="utf-8")

        result = TextFileProcessor.extract_text(str(test_file))
        assert result == content

    def test_extract_text_multiline(self, temp_dir):
        """Test extracting multiline text"""
        test_file = temp_dir / "test.txt"
        content = "Line 1\nLine 2\nLine 3"
        test_file.write_text(content, encoding="utf-8")

        result = TextFileProcessor.extract_text(str(test_file))
        assert result == content

    def test_extract_text_unicode(self, temp_dir):
        """Test extracting Unicode text"""
        test_file = temp_dir / "test.txt"
        content = "Hello World Earth"
        test_file.write_text(content, encoding="utf-8")

        result = TextFileProcessor.extract_text(str(test_file))
        assert result == content

    def test_extract_text_empty_file(self, temp_dir):
        """Test extracting empty file"""
        test_file = temp_dir / "empty.txt"
        test_file.write_text("", encoding="utf-8")

        result = TextFileProcessor.extract_text(str(test_file))
        assert result == ""

    def test_extract_text_gbk_encoding(self, temp_dir):
        """Test extracting GBK encoded file"""
        test_file = temp_dir / "test_gbk.txt"
        content = "Testing GBK encoding"
        test_file.write_text(content, encoding="gbk")

        result = TextFileProcessor.extract_text(str(test_file))
        assert result == content
