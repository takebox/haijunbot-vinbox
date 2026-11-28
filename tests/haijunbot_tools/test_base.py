# -*- coding: utf-8 -*-
"""Unit tests for haijunbot_tools.base module"""

from haijunbot.haijunbot_tools.base import Tool


class TestTool:
    """Tests for Tool class"""

    def test_init(self):
        """Test Tool initialization"""

        def test_func(args):
            return {"success": True, "stdout": "test"}

        tool = Tool(
            name="test_tool",
            description="Test tool",
            parameters={"type": "object"},
            func=test_func,
        )

        assert tool.name == "test_tool"
        assert tool.description == "Test tool"
        assert tool.parameters == {"type": "object"}
        assert tool.func == test_func
        assert tool.protocol_version == "1.0"

    def test_init_with_protocol_version(self):
        """Test initialization with protocol version"""

        def test_func(args):
            return {"success": True}

        tool = Tool(
            name="test_tool",
            description="Test tool",
            parameters={"type": "object"},
            func=test_func,
            protocol_version="2.0",
        )

        assert tool.protocol_version == "2.0"

    def test_to_dict(self):
        """Test to_dict method"""

        def test_func(args):
            return {"success": True}

        tool = Tool(
            name="test_tool",
            description="Test tool",
            parameters={"type": "object", "properties": {"arg1": {"type": "string"}}},
            func=test_func,
        )

        result = tool.to_dict()
        assert result["name"] == "test_tool"
        assert result["description"] == "Test tool"
        assert "parameters" in result
        # Verify parameters is a JSON string
        import json

        params = json.loads(result["parameters"])
        assert params["type"] == "object"

    def test_execute_success(self):
        """Test execute method successful execution"""

        def test_func(args):
            return {"success": True, "stdout": "test output", "stderr": ""}

        tool = Tool(
            name="test_tool",
            description="Test tool",
            parameters={"type": "object"},
            func=test_func,
        )

        result = tool.execute({"arg1": "value1"})
        assert result["success"] is True
        assert result["stdout"] == "test output"

    def test_execute_with_exception(self):
        """Test execute method handling exceptions"""

        def test_func(args):
            raise ValueError("Test error")

        tool = Tool(
            name="test_tool",
            description="Test tool",
            parameters={"type": "object"},
            func=test_func,
        )

        result = tool.execute({"arg1": "value1"})
        assert result["success"] is False
        assert "stderr" in result
        assert "execution failed" in result["stderr"].lower()
        assert "Test error" in result["stderr"]

    def test_execute_with_empty_arguments(self):
        """Test execution with empty arguments"""

        def test_func(args):
            return {"success": True, "stdout": "empty", "stderr": ""}

        tool = Tool(
            name="test_tool",
            description="Test tool",
            parameters={"type": "object"},
            func=test_func,
        )

        result = tool.execute({})
        assert result["success"] is True
