# -*- coding: utf-8 -*-
"""tool_executor unit tests"""

from unittest.mock import Mock, patch
import pytest

from haijunbot.haijunbot_agent.tool_executor import execute_tool_call


class TestToolExecutor:
    """Tests for tool_executor function"""

    @pytest.fixture
    def mock_agent(self):
        """Create mock Agent object"""
        agent = Mock()
        agent.execute_tool_confirm = False  # No confirmation needed by default
        agent.output_handler = []
        return agent

    @pytest.fixture
    def mock_handler(self):
        """Create mock output handler"""
        handler = Mock()
        handler.name.return_value = "MockTool"
        handler.can_handle.return_value = True
        handler.handle.return_value = (True, "Success result")
        return handler

    def test_no_matching_handler(self, mock_agent):
        """Test when there is no matching handler"""
        # Set up a non-matching handler
        handler = Mock()
        handler.can_handle.return_value = False
        mock_agent.output_handler = [handler]

        result = execute_tool_call("some command", mock_agent)

        assert result == (False, "")
        handler.can_handle.assert_called_once_with("some command")

    def test_single_handler_execution(self, mock_agent, mock_handler):
        """Test execution of a single handler"""
        mock_agent.output_handler = [mock_handler]

        with patch("haijunbot.haijunbot_utils.output.PrettyOutput.auto_print"):
            result = execute_tool_call("test command", mock_agent)

        # Verify result
        assert result == (True, "Success result")

        # Verify calls
        mock_handler.can_handle.assert_called_once_with("test command")
        mock_handler.handle.assert_called_once_with("test command", mock_agent)

        # Verify printed output - execution completion message has been removed, no longer verified

    @patch("haijunbot.haijunbot_utils.output.PrettyOutput.auto_print")
    def test_multiple_handlers_error(self, mock_print, mock_agent):
        """Test error when multiple handlers match"""
        # Create two matching handlers
        handler1 = Mock()
        handler1.can_handle.return_value = True
        handler1.name.return_value = "Tool1"

        handler2 = Mock()
        handler2.can_handle.return_value = True
        handler2.name.return_value = "Tool2"

        mock_agent.output_handler = [handler1, handler2]

        result = execute_tool_call("test command", mock_agent)

        # Verify result
        assert result[0] is False
        assert "multiple operations of different types detected" in result[1].lower()
        assert "Tool1" in result[1]
        assert "Tool2" in result[1]

        # Verify warning output
        mock_print.assert_called_once()
        args = mock_print.call_args[0]
        assert "multiple operations of different types detected" in args[0].lower()

    @patch("haijunbot.haijunbot_agent.tool_executor.user_confirm")
    def test_execution_with_confirmation_yes(
        self, mock_confirm, mock_agent, mock_handler
    ):
        """Test case where confirmation is needed and user confirms"""
        mock_agent.execute_tool_confirm = True
        mock_agent.output_handler = [mock_handler]
        mock_confirm.return_value = True

        with patch("builtins.print"):
            result = execute_tool_call("test command", mock_agent)

        # Verify result
        assert result == (True, "Success result")

        # Verify confirmation call
        mock_confirm.assert_called_once_with("Execute MockTool? Confirm execution?", True)

        # Verify tool execution
        mock_handler.handle.assert_called_once()

    @patch("haijunbot.haijunbot_agent.tool_executor.user_confirm")
    def test_execution_with_confirmation_no(
        self, mock_confirm, mock_agent, mock_handler
    ):
        """Test case where confirmation is needed but user declines"""
        mock_agent.execute_tool_confirm = True
        mock_agent.output_handler = [mock_handler]
        mock_confirm.return_value = False

        result = execute_tool_call("test command", mock_agent)

        # Verify result
        assert result == (False, "")

        # Verify confirmation call
        mock_confirm.assert_called_once()

        # Verify tool was not executed
        mock_handler.handle.assert_not_called()

    def test_handler_execution_failure(self, mock_agent, mock_handler):
        """Test case where handler execution fails"""
        mock_agent.output_handler = [mock_handler]
        mock_handler.handle.return_value = (False, "Execution failed")

        with patch("builtins.print"):
            result = execute_tool_call("test command", mock_agent)

        # Verify result
        assert result == (False, "Execution failed")

    def test_mixed_handlers_only_one_matches(self, mock_agent):
        """Test case with multiple handlers but only one matches"""
        # Create three handlers, only one matches
        handler1 = Mock()
        handler1.can_handle.return_value = False

        handler2 = Mock()
        handler2.can_handle.return_value = True
        handler2.name.return_value = "MatchingTool"
        handler2.handle.return_value = (True, "Result")

        handler3 = Mock()
        handler3.can_handle.return_value = False

        mock_agent.output_handler = [handler1, handler2, handler3]

        with patch("builtins.print"):
            result = execute_tool_call("test command", mock_agent)

        # Verify result
        assert result == (True, "Result")

        # Verify all handlers were checked
        handler1.can_handle.assert_called_once()
        handler2.can_handle.assert_called_once()
        handler3.can_handle.assert_called_once()

        # Verify only matching handler was executed
        handler2.handle.assert_called_once()
        handler1.handle.assert_not_called()
        handler3.handle.assert_not_called()

    def test_handler_output_keeps_only_final_visible_progress_state(
        self, mock_agent, mock_handler
    ):
        """Test that terminal progress output only preserves the final visible state."""
        mock_agent.output_handler = [mock_handler]
        mock_handler.handle.return_value = (
            True,
            "Downloading 10%\rDownloading 60%\rDownloading 100%\nDone\n",
        )

        result = execute_tool_call("test command", mock_agent)

        assert result == (True, "Downloading 100%\nDone")

    def test_handler_output_strips_ansi_sequences(self, mock_agent, mock_handler):
        """Test that ANSI control characters do not appear in final output."""
        mock_agent.output_handler = [mock_handler]
        mock_handler.handle.return_value = (
            True,
            "\x1b[32mSuccess\x1b[0m\n\x1b[31mWarning\x1b[0m",
        )

        result = execute_tool_call("test command", mock_agent)

        assert result == (True, "Success\nWarning")
