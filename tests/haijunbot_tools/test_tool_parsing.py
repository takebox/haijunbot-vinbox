# -*- coding: utf-8 -*-
"""Tests for tool parser recognition of different formats"""

from haijunbot.haijunbot_tools.registry import ToolRegistry


class TestToolParsing:
    """Tests for tool call parsing in various scenarios"""

    def test_parse_tool_with_name_prefix(self):
        """Test: tool name + code block format (should be recognized)"""
        content = """
        read_code
        ```json
        {
            "files": [{"path": "test.py"}]
        }
        ```
        """

        result, _, _ = ToolRegistry._extract_tool_calls(content)
        assert len(result) == 1
        assert result[0]["name"] == "read_code"
        assert result[0]["arguments"]["files"][0]["path"] == "test.py"

    def test_parse_bare_json_tool_call(self):
        """Test: bare JSON tool call (should be recognized)"""
        content = """
        This is some text
        {"name": "read_code", "arguments": {"files": [{"path": "test.py"}]}}
        More text
        """

        result, _, _ = ToolRegistry._extract_tool_calls(content)
        assert len(result) == 1
        assert result[0]["name"] == "read_code"

    def test_ignore_json_code_block_without_tool_name(self):
        """Test: standalone JSON code block (should not be recognized)"""
        content = """
        Here is example code:
        ```json
        {
            "name": "some_tool",
            "arguments": {"key": "value"}
        }
        ```
        """

        result, _, _ = ToolRegistry._extract_tool_calls(content)
        # Should not be recognized as a tool call
        assert len(result) == 0

    def test_ignore_example_in_documentation(self):
        """Test: examples in documentation (should not be recognized) - using unregistered tool names"""
        content = """
        ## Tool usage example

        ```json
        {
            "name": "example_tool_not_registered",
            "arguments": {
                "files": [{"file_path": "example.py"}]
            }
        }
        ```

        The above is an example format for tool calls.
        """

        result, _, _ = ToolRegistry._extract_tool_calls(content)
        assert len(result) == 0

    def test_parse_multiple_tools_mixed_format(self):
        """Test: multiple tool calls in mixed formats"""
        content = """
        First read the file:
        read_code
        ```json
        {"files": [{"path": "file1.py"}]}
        ```

        Then execute the script:
        {"name": "execute_script", "arguments": {"script_content": "echo test"}}
        """

        result, _, _ = ToolRegistry._extract_tool_calls(content)
        assert len(result) == 2
        tool_names = [r["name"] for r in result]
        assert "read_code" in tool_names
        assert "execute_script" in tool_names

    def test_parse_nested_json_in_code_block(self):
        """Test: nested JSON in code block (with tool name should be recognized)"""
        content = """
        edit_file
        ```json
        {
            "file_path": "test.py",
            "search": "old",
            "replace": "new"
        }
        ```
        """

        result, _, _ = ToolRegistry._extract_tool_calls(content)
        assert len(result) == 1
        assert result[0]["name"] == "edit_file"
        assert result[0]["arguments"]["file_path"] == "test.py"

    def test_ignore_incomplete_json_in_code_block(self):
        """Test: incomplete JSON in code block (should not be recognized)"""
        content = """
        Here is an example:
        ```json
        {
            "name": "xxx",
            ....
        }
        ```
        """

        result, _, _ = ToolRegistry._extract_tool_calls(content)
        assert len(result) == 0

    def test_parse_tool_with_language_hint(self):
        """Test: code block with language hint + tool name"""
        content = """
        read_code
        ```python
        {"files": [{"path": "test.py"}]}
        ```
        """

        result, _, _ = ToolRegistry._extract_tool_calls(content)
        assert len(result) == 1
        assert result[0]["name"] == "read_code"

    def test_ignore_code_block_with_non_json_content(self):
        """Test: code block with non-JSON content (should not be recognized)"""
        content = """
        Code example:
        ```python
        def hello():
            print("hello")
        ```
        """

        result, _, _ = ToolRegistry._extract_tool_calls(content)
        assert len(result) == 0

    def test_real_world_scenario_with_explanation(self):
        """Test: real scenario - reply containing explanation and tool call"""
        content = """
        OK, let me read this file.

        read_code
        ```json
        {
            "files": [{
                "path": "src/main.py",
                "start_line": 1,
                "end_line": 50
            }]
        }
        ```

        This tool reads the first 50 lines of the file.
        """

        result, _, _ = ToolRegistry._extract_tool_calls(content)
        assert len(result) == 1
        assert result[0]["name"] == "read_code"
        assert result[0]["arguments"]["files"][0]["path"] == "src/main.py"

    def test_parse_tool_call_xml_format_with_json_object(self):
        """Test: <tool_call name="..."> JSON object format (should be recognized)"""
        content = """
        <tool_call name="read_code">
        {"files": [{"path": "test.py"}]}
        </tool_call>
        """

        result, _, _ = ToolRegistry._extract_tool_calls(content)
        assert len(result) == 1
        assert result[0]["name"] == "read_code"
        assert result[0]["arguments"]["files"][0]["path"] == "test.py"

    def test_parse_tool_call_xml_format_with_json_array(self):
        """Test: <tool_call name="..."> JSON array format (should be recognized)"""
        content = """
        <tool_call name="edit_file">
        [
            {"file_path": "a.py", "search": "old", "replace": "new"},
            {"file_path": "b.py", "search": "x", "replace": "y"}
        ]
        </tool_call>
        """

        result, _, _ = ToolRegistry._extract_tool_calls(content)
        assert len(result) == 1
        assert result[0]["name"] == "edit_file"
        assert len(result[0]["arguments"]) == 2
        assert result[0]["arguments"][0]["file_path"] == "a.py"
        assert result[0]["arguments"][1]["file_path"] == "b.py"
