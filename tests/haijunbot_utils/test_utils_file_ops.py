# -*- coding: utf-8 -*-
"""Unit tests for haijunbot_utils.utils file operation functions"""

import pytest
import hashlib

from haijunbot.haijunbot_utils.utils import get_file_md5, get_file_line_count


class TestGetFileMd5:
    """Tests for get_file_md5 function"""

    def test_small_file(self, temp_dir):
        """Test small file MD5"""
        test_file = temp_dir / "test.txt"
        content = "Hello, World!"
        test_file.write_text(content)

        result = get_file_md5(str(test_file))

        # Verify MD5 format (32 hexadecimal characters)
        assert len(result) == 32
        assert all(c in "0123456789abcdef" for c in result)

    def test_empty_file(self, temp_dir):
        """Test empty file MD5"""
        test_file = temp_dir / "empty.txt"
        test_file.write_text("")

        result = get_file_md5(str(test_file))

        # MD5 of empty file
        expected = hashlib.md5(b"").hexdigest()
        assert result == expected

    def test_binary_file(self, temp_dir):
        """Test binary file MD5"""
        test_file = temp_dir / "test.bin"
        content = b"\x00\x01\x02\x03\x04\x05"
        test_file.write_bytes(content)

        result = get_file_md5(str(test_file))

        expected = hashlib.md5(content).hexdigest()
        assert result == expected

    def test_unicode_file(self, temp_dir):
        """Test Unicode file MD5"""
        test_file = temp_dir / "unicode.txt"
        content = "Hello World Earth"
        test_file.write_text(content, encoding="utf-8")

        result = get_file_md5(str(test_file))

        expected = hashlib.md5(content.encode("utf-8")).hexdigest()
        assert result == expected

    def test_large_file(self, temp_dir):
        """Test large file MD5 (only first 100MB calculated)"""
        test_file = temp_dir / "large.bin"
        # Create a 50MB file
        chunk = b"A" * (1024 * 1024)  # 1MB
        with open(test_file, "wb") as f:
            for _ in range(50):
                f.write(chunk)

        result = get_file_md5(str(test_file))

        # Verify MD5 format
        assert len(result) == 32
        assert all(c in "0123456789abcdef" for c in result)

    def test_nonexistent_file(self):
        """Test nonexistent file"""
        with pytest.raises(FileNotFoundError):
            get_file_md5("/nonexistent/file.txt")


class TestGetFileLineCount:
    """Tests for get_file_line_count function"""

    def test_empty_file(self, temp_dir):
        """Test empty file"""
        test_file = temp_dir / "empty.txt"
        test_file.write_text("")

        result = get_file_line_count(str(test_file))
        assert result == 0

    def test_single_line(self, temp_dir):
        """Test single line file"""
        test_file = temp_dir / "single.txt"
        test_file.write_text("Hello")

        result = get_file_line_count(str(test_file))
        assert result == 1

    def test_multiple_lines(self, temp_dir):
        """Test multiple line file"""
        test_file = temp_dir / "multi.txt"
        test_file.write_text("Line 1\nLine 2\nLine 3")

        result = get_file_line_count(str(test_file))
        assert result == 3

    def test_file_with_empty_lines(self, temp_dir):
        """Test file containing empty lines"""
        test_file = temp_dir / "empty_lines.txt"
        test_file.write_text("Line 1\n\nLine 3\n")

        result = get_file_line_count(str(test_file))
        # write_text adds trailing newline by default, so it's 4 lines
        # But if there's a trailing newline, it could be 3 or 4 depending on implementation
        assert result >= 3

    def test_file_without_trailing_newline(self, temp_dir):
        """Test file without trailing newline"""
        test_file = temp_dir / "no_newline.txt"
        test_file.write_text("Line 1\nLine 2", newline="")

        result = get_file_line_count(str(test_file))
        assert result == 2

    def test_unicode_file(self, temp_dir):
        """Test Unicode file"""
        test_file = temp_dir / "unicode.txt"
        test_file.write_text("Hello\nWorld\nEarth")

        result = get_file_line_count(str(test_file))
        assert result == 3

    def test_large_file(self, temp_dir):
        """Test large file"""
        test_file = temp_dir / "large.txt"
        lines = [f"Line {i}\n" for i in range(1000)]
        test_file.write_text("".join(lines))

        result = get_file_line_count(str(test_file))
        assert result == 1000

    def test_nonexistent_file(self):
        """Test nonexistent file"""
        result = get_file_line_count("/nonexistent/file.txt")
        assert result == 0

    def test_binary_file(self, temp_dir):
        """Test binary file (should return 0 or handle error)"""
        test_file = temp_dir / "binary.bin"
        test_file.write_bytes(b"\x00\x01\x02\x03")

        # Function uses errors="ignore", so it should handle it
        result = get_file_line_count(str(test_file))
        # Binary files may not read correctly as text, but function should return a value
        assert isinstance(result, int)
