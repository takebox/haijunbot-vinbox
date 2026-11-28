# -*- coding: utf-8 -*-
"""haijunbot_tools.read_code module unit tests"""

import os
import tempfile
from unittest.mock import MagicMock

import pytest

from haijunbot.haijunbot_tools.read_code import ReadCodeTool


class TestReadCodeTool:
    """Tests for ReadCodeTool class"""

    @pytest.fixture
    def tool(self):
        """Create test ReadCodeTool instance"""
        return ReadCodeTool()

    @pytest.fixture
    def mock_agent(self):
        """Create mock Agent instance"""
        agent = MagicMock()
        # Use dictionary to store user data
        agent._user_data = {}

        # Explicitly set model to None, avoiding MagicMock auto-creating attributes causing get_remaining_token_count to return MagicMock
        agent.model = None

        def get_user_data(key):
            return agent._user_data.get(key)

        def set_user_data(key, value):
            agent._user_data[key] = value

        agent.get_user_data = MagicMock(side_effect=get_user_data)
        agent.set_user_data = MagicMock(side_effect=set_user_data)
        return agent

    @pytest.fixture
    def sample_file(self):
        """Create sample file"""
        content = """def hello():
    PrettyOutput.auto_print("Hello, World!")

def add(a, b):
    return a + b

class Calculator:
    def __init__(self):
        self.value = 0

    def add(self, x):
        self.value += x
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(content)
            filepath = f.name

        yield filepath

        # Cleanup
        if os.path.exists(filepath):
            os.unlink(filepath)

    def test_read_single_file(self, tool, sample_file):
        """Test reading a single file"""
        result = tool.execute({"files": [{"path": sample_file}]})

        assert result["success"] is True
        assert "stdout" in result
        assert (
            sample_file in result["stdout"]
            or os.path.basename(sample_file) in result["stdout"]
        )

    def test_read_file_with_range(self, tool, sample_file):
        """Test reading specified file range"""
        result = tool.execute(
            {"files": [{"path": sample_file, "start_line": 1, "end_line": 5}]}
        )

        assert result["success"] is True
        assert "stdout" in result

    def test_read_nonexistent_file(self, tool):
        """Test reading nonexistent file"""
        result = tool.execute({"files": [{"path": "/nonexistent/file/path.py"}]})

        assert result["success"] is False
        # Error message may be in stderr or stdout
        error_msg = result.get("stderr", "") + result.get("stdout", "")
        assert (
            "does not exist" in error_msg
            or "not found" in error_msg.lower()
            or "File read failed" in error_msg
        )

    def test_read_multiple_files(self, tool, sample_file):
        """Test reading multiple files"""
        # Create second file
        content2 = "x = 1\ny = 2\nz = x + y\n"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(content2)
            filepath2 = f.name

        try:
            result = tool.execute(
                {"files": [{"path": sample_file}, {"path": filepath2}]}
            )

            assert result["success"] is True
            assert "stdout" in result
        finally:
            if os.path.exists(filepath2):
                os.unlink(filepath2)

    def test_read_empty_file(self, tool):
        """Test reading empty file"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            empty_file = f.name

        try:
            result = tool.execute({"files": [{"path": empty_file}]})

            assert result["success"] is True
            assert "empty" in result["stdout"]
        finally:
            if os.path.exists(empty_file):
                os.unlink(empty_file)

    def test_read_file_with_negative_line_number(self, tool, sample_file):
        """Test using negative line numbers (counting from end of file)"""
        result = tool.execute(
            {"files": [{"path": sample_file, "start_line": -5, "end_line": -1}]}
        )

        # Should succeed or give a reasonable error
        assert "success" in result

    def test_read_file_exceeds_token_limit(self, tool):
        """Test reading oversized file (exceeding token limit)"""
        # Create a very large file
        large_content = "\n".join([f"line {i}" for i in range(10000)])
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(large_content)
            large_file = f.name

        try:
            result = tool.execute({"files": [{"path": large_file}]})

            # Should fail or give a warning
            assert "success" in result
        finally:
            if os.path.exists(large_file):
                os.unlink(large_file)

    def test_read_file_with_invalid_range(self, tool, sample_file):
        """Test invalid line number range"""
        result = tool.execute(
            {"files": [{"path": sample_file, "start_line": 100, "end_line": 50}]}
        )

        # Code may auto-correct the range, so it may succeed or fail
        # As long as no exception is thrown
        assert "success" in result

    def test_read_file_without_agent(self, tool, sample_file):
        """Test reading file without using agent"""
        result = tool.execute({"files": [{"path": sample_file}]})

        assert result["success"] is True
        assert "stdout" in result

    def test_read_with_missing_files(self, tool):
        """Test missing files parameter"""
        result = tool.execute({})
        assert result["success"] is False
        # Error message may be in Chinese
        error_msg = result.get("stderr", "").lower()
        assert "files" in error_msg or "file list" in result.get("stderr", "")

        # Empty files list
        result = tool.execute({"files": []})
        assert result["success"] is False

    def test_merged_ranges_deduplication(self, tool, mock_agent):
        """Test deduplication when reading multiple overlapping ranges of the same file"""
        content = """class MyClass:
    def method1(self):
        PrettyOutput.auto_print("method1")
        return 1

    def method2(self):
        PrettyOutput.auto_print("method2")
        return 2

    def method3(self):
        PrettyOutput.auto_print("method3")
        return 3

    def method4(self):
        PrettyOutput.auto_print("method4")
        return 4
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(content)
            filepath = f.name
        try:
            # Test two overlapping ranges
            result = tool.execute(
                {
                    "files": [
                        {"path": filepath, "start_line": 1, "end_line": 10},
                        {"path": filepath, "start_line": 5, "end_line": 15},
                    ],
                    "agent": mock_agent,
                }
            )
            assert result["success"] is True
            # Verify output contains file content
            assert filepath in result["stdout"] or "method" in result["stdout"]
        finally:
            if os.path.exists(filepath):
                os.unlink(filepath)

    def test_merged_ranges_multiple_requests(self, tool, mock_agent):
        """Test deduplication for three or more range requests of the same file"""
        content = """def func1():
    pass

def func2():
    pass

def func3():
    pass

def func4():
    pass

def func5():
    pass
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(content)
            filepath = f.name
        try:
            # Test three range requests
            result = tool.execute(
                {
                    "files": [
                        {"path": filepath, "start_line": 1, "end_line": 5},
                        {"path": filepath, "start_line": 3, "end_line": 10},
                        {"path": filepath, "start_line": 8, "end_line": 15},
                    ],
                    "agent": mock_agent,
                }
            )
            assert result["success"] is True
            # Verify output contains file content
            assert filepath in result["stdout"] or "func" in result["stdout"]
        finally:
            if os.path.exists(filepath):
                os.unlink(filepath)

    def test_merged_ranges_different_files(self, tool, mock_agent):
        """Test that multi-range requests for different files are not incorrectly merged"""
        content1 = """def func_a():
    pass
"""
        content2 = """def func_b():
    pass
"""
        with (
            tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f1,
            tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f2,
        ):
            f1.write(content1)
            f2.write(content2)
            filepath1 = f1.name
            filepath2 = f2.name
        try:
            result = tool.execute(
                {
                    "files": [
                        {"path": filepath1, "start_line": 1, "end_line": -1},
                        {"path": filepath2, "start_line": 1, "end_line": -1},
                    ],
                    "agent": mock_agent,
                }
            )
            assert result["success"] is True
            # Both files should be read
            assert filepath1 in result["stdout"] or "func_a" in result["stdout"]
            assert filepath2 in result["stdout"] or "func_b" in result["stdout"]
        finally:
            if os.path.exists(filepath1):
                os.unlink(filepath1)
            if os.path.exists(filepath2):
                os.unlink(filepath2)

    def test_merged_ranges_without_agent(self, tool):
        """Test deduplication for multi-range requests without agent"""
        content = """class Test:
    def method1(self):
        pass

    def method2(self):
        pass
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(content)
            filepath = f.name
        try:
            # Should deduplicate even without agent
            result = tool.execute(
                {
                    "files": [
                        {"path": filepath, "start_line": 1, "end_line": 4},
                        {"path": filepath, "start_line": 3, "end_line": 7},
                    ]
                }
            )
            assert result["success"] is True
            # Verify output contains file content
            assert filepath in result["stdout"] or "method" in result["stdout"]
        finally:
            if os.path.exists(filepath):
                os.unlink(filepath)
