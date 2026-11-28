# -*- coding: utf-8 -*-
"""haijunbot_tools.registry module unit tests"""

import pytest
from unittest.mock import MagicMock

from haijunbot.haijunbot_tools.registry import ToolRegistry
from haijunbot.haijunbot_tools.base import Tool


class TestToolRegistry:
    """Tests for ToolRegistry class"""

    @pytest.fixture
    def registry(self):
        """Create test ToolRegistry instance"""
        reg = ToolRegistry()
        # Clear auto-loaded tools, only test tools we register
        reg.tools.clear()
        return reg

    @pytest.fixture
    def sample_tool(self):
        """Create sample tool"""

        def tool_func(args):
            return {"success": True, "stdout": "test output", "stderr": ""}

        return Tool(
            name="test_tool",
            description="Test tool",
            parameters={"type": "object"},
            func=tool_func,
        )

    def test_init(self, registry):
        """Test initialization"""
        assert registry is not None
        assert hasattr(registry, "tools")
        assert isinstance(registry.tools, dict)

    def test_register_tool(self, registry, sample_tool):
        """Test registering tool"""
        registry.register_tool(
            sample_tool.name,
            sample_tool.description,
            sample_tool.parameters,
            sample_tool.func,
        )
        assert "test_tool" in registry.tools
        assert registry.tools["test_tool"].name == "test_tool"

    def test_get_tool_existing(self, registry, sample_tool):
        """Test getting existing tool"""
        registry.register_tool(
            sample_tool.name,
            sample_tool.description,
            sample_tool.parameters,
            sample_tool.func,
        )
        tool = registry.get_tool("test_tool")
        assert tool is not None
        assert tool.name == "test_tool"

    def test_get_tool_nonexistent(self, registry):
        """Test getting nonexistent tool"""
        tool = registry.get_tool("nonexistent_tool")
        assert tool is None

    def test_get_all_tools(self, registry, sample_tool):
        """Test getting all tools"""
        registry.register_tool(
            sample_tool.name,
            sample_tool.description,
            sample_tool.parameters,
            sample_tool.func,
        )
        tools = registry.get_all_tools()
        assert isinstance(tools, list)
        assert len(tools) > 0
        # Check tool dict format
        tool_dict = next((t for t in tools if t["name"] == "test_tool"), None)
        assert tool_dict is not None
        assert tool_dict["name"] == "test_tool"
        assert tool_dict["description"] == "Test tool"

    def test_execute_tool_success(self, registry, sample_tool):
        """Test successful tool execution"""
        registry.register_tool(
            sample_tool.name,
            sample_tool.description,
            sample_tool.parameters,
            sample_tool.func,
        )
        result = registry.execute_tool("test_tool", {"arg1": "value1"})
        assert result["success"] is True
        assert "stdout" in result

    def test_execute_tool_nonexistent(self, registry):
        """Test executing nonexistent tool"""
        result = registry.execute_tool("nonexistent_tool", {})
        assert result["success"] is False
        assert "stderr" in result
        assert "does not exist" in result["stderr"]

    def test_execute_tool_with_agent_v1(self, registry, sample_tool):
        """Test executing tool with v1.0 protocol (with agent)"""
        registry.register_tool(
            sample_tool.name,
            sample_tool.description,
            sample_tool.parameters,
            sample_tool.func,
        )
        mock_agent = MagicMock()
        result = registry.execute_tool(
            "test_tool", {"arg1": "value1"}, agent=mock_agent
        )
        assert result["success"] is True

    def test_execute_tool_with_agent_v2(self, registry):
        """Test executing tool with v2.0 protocol"""

        def v2_tool_func(args, agent):
            return {"success": True, "stdout": "v2 output", "stderr": ""}

        registry.register_tool(
            "v2_tool",
            "V2 tool",
            {"type": "object"},
            v2_tool_func,
            protocol_version="2.0",
        )

        mock_agent = MagicMock()
        result = registry.execute_tool("v2_tool", {"arg1": "value1"}, agent=mock_agent)
        assert result["success"] is True
        assert result["stdout"] == "v2 output"

    def test_execute_tool_exception(self, registry):
        """Test tool execution exception"""

        def failing_tool(args):
            raise ValueError("Tool error")

        registry.register_tool(
            "failing_tool", "Failing tool", {"type": "object"}, failing_tool
        )

        result = registry.execute_tool("failing_tool", {})
        assert result["success"] is False
        assert "stderr" in result

    def test_parse_special_marker_format_with_end_marker(self):
        """Test parsing special marker format (with end marker)"""
        content = """<|tool_calls_section_begin|>
<|tool_call_begin|>functions.read_code:0<|tool_call_argument_begin|>
{"files": [{"path": "test.py"}]}
<|tool_call_end|>
"""
        result = ToolRegistry._parse_special_marker_format(content)
        assert len(result) == 1
        assert result[0]["name"] == "read_code"
        assert result[0]["arguments"] == {"files": [{"path": "test.py"}]}

    def test_parse_special_marker_format_without_end_marker(self):
        """Test parsing special marker format (without end marker)"""
        content = '<|tool_call_begin|>functions.execute_script:1<|tool_call_argument_begin|>{"script_content": "echo hello"}'
        result = ToolRegistry._parse_special_marker_format(content)
        assert len(result) == 1
        assert result[0]["name"] == "execute_script"
        assert result[0]["arguments"] == {"script_content": "echo hello"}

    def test_parse_special_marker_format_multiple_calls(self):
        """Test parsing multiple tool calls"""
        content = """<|tool_call_begin|>functions.read_code:0<|tool_call_argument_begin|>
{"files": [{"path": "a.py"}]}
<|tool_call_end|>
<|tool_call_begin|>functions.edit_file:1<|tool_call_argument_begin|>
{"files": [{"file_path": "b.py"}]}
<|tool_call_end|>
"""
        result = ToolRegistry._parse_special_marker_format(content)
        assert len(result) == 2
        assert result[0]["name"] == "read_code"
        assert result[1]["name"] == "edit_file"

    def test_parse_special_marker_format_invalid_json(self):
        """Test parsing invalid JSON"""
        content = """<|tool_call_begin|>functions.test_tool:0<|tool_call_argument_begin|>
{invalid json}
<|tool_call_end|>
"""
        result = ToolRegistry._parse_special_marker_format(content)
        # Invalid JSON should be skipped, returning empty list
        assert len(result) == 0

    def test_extract_tool_calls_with_special_marker(self):
        """Test _extract_tool_calls correctly parses special marker format"""
        content = '<|tool_call_begin|>functions.read_code:0<|tool_call_argument_begin|>{"files": [{"path": "test.py"}]}<|tool_call_end|>'
        result, error, auto_completed = ToolRegistry._extract_tool_calls(content)
        assert error == ""
        # _extract_tool_calls always returns list
        assert len(result) == 1
        assert result[0]["name"] == "read_code"
        assert result[0]["arguments"] == {"files": [{"path": "test.py"}]}

    def test_parse_tool_name_json_format_basic(self):
        """Test parsing tool name + JSON format: tool_name\n{JSON params}"""
        content = 'read_code\n{"files": [{"path": "test.py"}]}'
        result = ToolRegistry._parse_tool_name_json_format(content)
        assert len(result) == 1
        assert result[0]["name"] == "read_code"
        assert result[0]["arguments"] == {"files": [{"path": "test.py"}]}

    def test_parse_tool_name_json_format_with_nested_json(self):
        """Test parsing tool name + nested JSON format (two levels nested)"""
        content = (
            'execute_script\n{"interpreter": "bash", "script_content": "echo hello"}'
        )
        result = ToolRegistry._parse_tool_name_json_format(content)
        assert len(result) == 1
        assert result[0]["name"] == "execute_script"
        assert result[0]["arguments"] == {
            "interpreter": "bash",
            "script_content": "echo hello",
        }

    def test_parse_xml_parameter_format_basic(self):
        """Test parsing XML parameter tag format: <tool_name><parameter name="key">value</parameter></tool_name>"""
        content = '<read_code>\n<parameter name="files">[{"path": "test.py"}]</parameter>\n</read_code>'
        result = ToolRegistry._parse_xml_parameter_format(content, [])
        assert len(result) == 1
        assert result[0]["name"] == "read_code"
        assert result[0]["arguments"] == {"files": [{"path": "test.py"}]}

    def test_parse_xml_parameter_format_multiple_params(self):
        """Test parsing XML parameter tag format: multiple parameter subtags"""
        content = '<execute_script>\n<parameter name="interpreter">bash</parameter>\n<parameter name="script_content">echo hello</parameter>\n</execute_script>'
        result = ToolRegistry._parse_xml_parameter_format(content, [])
        assert len(result) == 1
        assert result[0]["name"] == "execute_script"
        assert result[0]["arguments"]["interpreter"] == "bash"
        assert result[0]["arguments"]["script_content"] == "echo hello"

    def test_extract_tool_calls_with_tool_name_json_format(self):
        """Test _extract_tool_calls correctly parses tool name + JSON format"""
        content = 'read_code\n{"files": [{"path": "test.py"}]}'
        result, error, _ = ToolRegistry._extract_tool_calls(content)
        assert error == ""
        assert len(result) == 1
        assert result[0]["name"] == "read_code"
        assert result[0]["arguments"] == {"files": [{"path": "test.py"}]}

    def test_extract_tool_calls_with_xml_parameter_format(self):
        """Test _extract_tool_calls correctly parses XML parameter tag format"""
        content = '<execute_script>\n<parameter name="interpreter">bash</parameter>\n<parameter name="script_content">grep -n pattern file</parameter>\n</execute_script>'
        result, error, _ = ToolRegistry._extract_tool_calls(content)
        assert error == ""
        assert len(result) == 1
        assert result[0]["name"] == "execute_script"
        assert result[0]["arguments"]["interpreter"] == "bash"
        assert result[0]["arguments"]["interpreter"] == "bash"
        assert result[0]["arguments"]["script_content"] == "grep -n pattern file"

    # ────────────── _compress_output tests ──────────────

    def test_compress_output_empty(self, registry):
        """Test empty string and special markers returned directly"""
        assert registry._compress_output("") == ""
        assert registry._compress_output("<no output or errors>") == "<no output or errors>"

    # Layer 1 blank line collapse disabled
    # def test_compress_output_blank_lines_collapse(self, registry):
    #     """Layer 1: consecutive blank lines >= 3 collapsed to 2"""
    #     text = "line1\n\n\n\n\nline2"
    #     result = registry._compress_output(text)
    #     # 5 blank lines collapsed to 2
    #     assert result == "line1\n\n\nline2"

    # Layer 1 blank line collapse disabled
    # def test_compress_output_blank_lines_keep(self, registry):
    #     """Layer 1: consecutive blank lines < 3 unchanged"""
    #     text = "line1\n\n\nline2"
    #     result = registry._compress_output(text)
    #     # 2 blank lines not collapsed
    #     assert result == "line1\n\n\nline2"

    def test_compress_output_json_compress(self, registry):
        """Layer 2: JSON compression effective (compression ratio < 70%)"""
        text = '<stdout>\n{\n  "key": "value",\n  "nested": {\n    "a": 1\n  }\n}\n</stdout>'
        result = registry._compress_output(text)
        # After compression should become single-line JSON
        assert "<stdout>" in result
        assert "</stdout>" in result
        assert '{"key":"value","nested":{"a":1}}' in result
        assert '\n  "key"' not in result

    def test_compress_output_json_no_compress(self, registry):
        """Layer 2: Already compact JSON / non-JSON / invalid JSON not compressed"""
        # Already compact JSON (compression ratio >= 70%)
        compact_text = '<stdout>\n{"a":"b"}\n</stdout>'
        result = registry._compress_output(compact_text)
        assert result == compact_text  # Unchanged
        # Non-JSON text
        plain_text = "<stdout>\njust a normal text\n</stdout>"
        result = registry._compress_output(plain_text)
        assert result == plain_text  # Unchanged

    def test_compress_output_repeated_lines(self, registry):
        """Layer 3: consecutive repeated lines >= 4 merged"""
        text = "header\ndata_line\ndata_line\ndata_line\ndata_line\ndata_line\nfooter"
        result = registry._compress_output(text)
        lines = result.split("\n")
        assert lines[0] == "header"
        assert lines[1] == "data_line"
        assert "...(above content repeated 4 times)" in lines[2]
        assert lines[3] == "footer"

    def test_compress_output_repeated_lines_few(self, registry):
        """Layer 3: consecutive repeated lines < 4 not compressed"""
        text = "a\nb\nb\nb\nc"
        result = registry._compress_output(text)
        assert result == text  # 3 repeats not compressed

    # Layer 4 line count safety boundary disabled
    # def test_compress_output_safety_boundary(self, registry):
    #     """Layer 4: keep first and last 100 lines when exceeding 200 lines"""
    #     lines = [f"line_{i}" for i in range(250)]
    #     text = "\n".join(lines)
    #     result = registry._compress_output(text)
    #     result_lines = result.split("\n")
    #     # Check if collapse marker included
    #     assert "lines collapsed" in result
    #     assert "total lines 250" in result
    #     # Check head/tail preservation
    #     assert "line_0" in result_lines[0]
    #     assert "line_99" in result_lines[99]
    #     # Check tail preservation
    #     assert "line_249" in result_lines[-1]
    #     assert "line_150" in result  # Tail start line appears in result
