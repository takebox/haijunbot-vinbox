# -*- coding: utf-8 -*-
"""Unit tests for prompt_builder"""

from unittest.mock import Mock
import pytest

from haijunbot.haijunbot_agent.prompt_builder import build_action_prompt


class TestPromptBuilder:
    """Tests for prompt_builder function"""

    @pytest.fixture
    def mock_handler(self):
        """Create mock output handler"""
        handler = Mock()
        handler.name.return_value = "TestTool"
        handler.prompt.return_value = """This is a test tool.
It does something useful.

Parameters:
- param1: description
- param2: description"""
        return handler

    def test_build_action_prompt_empty_handlers(self):
        """Test empty handler list"""
        result = build_action_prompt([])

        # Verify basic structure
        assert "<actions>" in result
        assert "Available Actions" in result
        assert "<overview>" in result
        assert "## Action List" in result
        assert "[]" in result  # Empty list
        assert "</overview>" in result
        assert "<rules>" in result
        assert "Important Rules" in result
        assert "</rules>" in result
        assert "</actions>" in result

    def test_build_action_prompt_single_handler(self, mock_handler):
        """Test single handler"""
        result = build_action_prompt([mock_handler])

        # Verify handler name in overview
        assert "[TestTool]" in result

        # Verify handler details
        assert "## TestTool" in result
        assert "This is a test tool." in result
        assert "It does something useful." in result
        assert "Parameters:" in result
        assert "- param1: description" in result
        assert "- param2: description" in result

        # Verify indentation (3 spaces before each line)
        assert "   This is a test tool." in result
        assert "   It does something useful." in result

    def test_build_action_prompt_multiple_handlers(self):
        """Test multiple handlers"""
        # Create three mock handlers
        handler1 = Mock()
        handler1.name.return_value = "Tool1"
        handler1.prompt.return_value = "Tool 1 description"

        handler2 = Mock()
        handler2.name.return_value = "Tool2"
        handler2.prompt.return_value = "Tool 2 description"

        handler3 = Mock()
        handler3.name.return_value = "Tool3"
        handler3.prompt.return_value = "Tool 3 description"

        handlers = [handler1, handler2, handler3]
        result = build_action_prompt(handlers)

        # Verify overview list
        assert "[Tool1, Tool2, Tool3]" in result

        # Verify details for each tool
        assert "## Tool1" in result
        assert "   Tool 1 description" in result
        assert "## Tool2" in result
        assert "   Tool 2 description" in result
        assert "## Tool3" in result
        assert "   Tool 3 description" in result

    def test_build_action_prompt_with_empty_lines(self):
        """Test handler descriptions containing empty lines"""
        handler = Mock()
        handler.name.return_value = "EmptyLineTool"
        handler.prompt.return_value = """First line

Third line

Fifth line"""

        result = build_action_prompt([handler])

        # Verify empty lines are preserved but without indentation
        lines = result.split("\n")

        # Find the tool description section
        tool_section_start = False
        for i, line in enumerate(lines):
            if "## EmptyLineTool" in line:
                tool_section_start = True
                # Check the next few lines
                assert lines[i + 1].strip() == "First line"
                assert lines[i + 2].strip() == ""  # Empty line
                assert lines[i + 3].strip() == "Third line"
                assert lines[i + 4].strip() == ""  # Empty line
                assert lines[i + 5].strip() == "Fifth line"
                break

        assert tool_section_start, "Tool section not found"

    def test_build_action_prompt_with_leading_trailing_whitespace(self):
        """Test handler descriptions with leading/trailing whitespace"""
        handler = Mock()
        handler.name.return_value = "WhitespaceTool"
        handler.prompt.return_value = "\n\n  Tool description  \n\n"

        result = build_action_prompt([handler])

        # Verify leading/trailing whitespace is stripped
        assert "## WhitespaceTool" in result
        assert "   Tool description" in result
        # Ensure no extra empty lines
        assert "\n\n\n" not in result
