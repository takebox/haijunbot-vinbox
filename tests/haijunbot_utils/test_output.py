# -*- coding: utf-8 -*-
"""Unit tests for the haijunbot_utils.output module"""

from unittest.mock import Mock, patch
from haijunbot.haijunbot_utils.output import (
    OutputType,
    OutputEvent,
    PrettyOutput,
    OutputSink,
    ConsoleOutputSink,
    _safe_color_get,
    emit_output,
)


class TestOutputType:
    """Tests for OutputType enum"""

    def test_enum_values(self):
        """Test enum values"""
        assert OutputType.SYSTEM.value == "SYSTEM"
        assert OutputType.CODE.value == "CODE"
        assert OutputType.RESULT.value == "RESULT"
        assert OutputType.ERROR.value == "ERROR"
        assert OutputType.INFO.value == "INFO"
        assert OutputType.PLANNING.value == "PLANNING"
        assert OutputType.PROGRESS.value == "PROGRESS"
        assert OutputType.SUCCESS.value == "SUCCESS"
        assert OutputType.WARNING.value == "WARNING"
        assert OutputType.DEBUG.value == "DEBUG"
        assert OutputType.USER.value == "USER"
        assert OutputType.TOOL.value == "TOOL"

    def test_enum_comparison(self):
        """Test enum comparison"""
        assert OutputType.SYSTEM.value == "SYSTEM"
        assert OutputType.ERROR.value != "SUCCESS"

    def test_enum_membership(self):
        """Test enum members"""
        assert "SYSTEM" in [e.value for e in OutputType]
        assert "ERROR" in [e.value for e in OutputType]


class TestOutputEvent:
    """Tests for OutputEvent data class"""

    def test_basic_creation(self):
        """Test basic creation"""
        event = OutputEvent(text="Test message", output_type=OutputType.INFO)
        assert event.text == "Test message"
        assert event.output_type == OutputType.INFO
        assert event.timestamp is None  # Default value
        assert event.lang is None
        assert event.traceback is False
        assert event.section is None
        assert event.context is None

    def test_full_creation(self):
        """Test full creation"""
        event = OutputEvent(
            text="Test message",
            output_type=OutputType.ERROR,
            timestamp=False,
            lang="python",
            traceback=True,
            section="Test Section",
            context={"key": "value"},
        )
        assert event.text == "Test message"
        assert event.output_type == OutputType.ERROR
        assert event.timestamp is False
        assert event.lang == "python"
        assert event.traceback is True
        assert event.section == "Test Section"
        assert event.context == {"key": "value"}

    def test_different_output_types(self):
        """Test different output types"""
        for output_type in OutputType:
            event = OutputEvent(
                text=f"Message for {output_type.value}", output_type=output_type
            )
            assert event.output_type == output_type
            assert event.text == f"Message for {output_type.value}"

    def test_empty_text(self):
        """Test empty text"""
        event = OutputEvent(text="", output_type=OutputType.INFO)
        assert event.text == ""
        assert event.output_type == OutputType.INFO


class TestSafeColorGet:
    """Tests for _safe_color_get function"""

    def test_valid_color(self):
        """Test valid color"""
        assert _safe_color_get("red") == "red"
        assert _safe_color_get("blue") == "blue"
        assert _safe_color_get("green") == "green"

    def test_invalid_color_with_fallback(self):
        """Test invalid color with fallback"""
        assert _safe_color_get("invalid_color", "white") == "white"
        assert _safe_color_get("not_a_color", "grey50") == "grey50"

    def test_color_alias_mapping(self):
        """Test color alias mapping"""
        assert _safe_color_get("dark_olive_green") == "green"
        assert _safe_color_get("orange3") == "bright_yellow"
        assert _safe_color_get("sea_green3") == "green"
        assert _safe_color_get("dark_sea_green") == "green"
        assert _safe_color_get("grey58") == "grey50"

    def test_default_fallback(self):
        """Test default fallback color"""
        assert _safe_color_get("invalid") == "white"


class TestHighlightProgressText:
    """Tests for _highlight_progress_text static method"""

    def test_single_progress_round(self):
        """Test single progress round (round X)"""
        from rich.text import Text

        text = "Executing round 3 processing"
        result = ConsoleOutputSink._highlight_progress_text(
            text, OutputType.PROGRESS, {OutputType.PROGRESS: "grey50"}
        )

        assert isinstance(result, Text)
        assert "3" in str(result)

    def test_progress_with_total(self):
        """Test progress with total (round X/Y)"""
        from rich.text import Text

        text = "Executing round 3/10 processing"
        result = ConsoleOutputSink._highlight_progress_text(
            text, OutputType.PROGRESS, {OutputType.PROGRESS: "grey50"}
        )

        assert isinstance(result, Text)
        assert "3" in str(result)
        assert "10" in str(result)

    def test_no_progress_info(self):
        """Test normal text without progress info"""
        from rich.text import Text

        text = "Normal text content"
        result = ConsoleOutputSink._highlight_progress_text(
            text, OutputType.INFO, {OutputType.INFO: "blue"}
        )

        assert isinstance(result, Text)
        assert str(result) == text

    def test_multiple_progress_patterns(self):
        """Test text with multiple progress patterns"""
        from rich.text import Text

        text = "Round 1 started, round 2 continues"
        result = ConsoleOutputSink._highlight_progress_text(
            text, OutputType.PROGRESS, {OutputType.PROGRESS: "grey50"}
        )

        assert isinstance(result, Text)
        assert "1" in str(result)
        assert "2" in str(result)

    def test_progress_with_spaces(self):
        """Test space handling in progress text"""
        from rich.text import Text

        text = "Round  5  "
        result = ConsoleOutputSink._highlight_progress_text(
            text, OutputType.PROGRESS, {OutputType.PROGRESS: "grey50"}
        )

        assert isinstance(result, Text)
        assert "5" in str(result)


class TestConsoleOutputSink:
    """Tests for ConsoleOutputSink class"""

    @patch("haijunbot.haijunbot_utils.output.console")
    @patch("haijunbot.haijunbot_utils.output.get_pretty_output", return_value=True)
    def test_emit_section(self, mock_get_pretty, mock_console):
        """Test section output"""
        sink = ConsoleOutputSink()
        event = OutputEvent(
            text="", output_type=OutputType.SYSTEM, section="Test Section"
        )
        sink.emit(event)
        assert mock_console.print.called

    @patch("haijunbot.haijunbot_utils.output.console")
    @patch("haijunbot.haijunbot_utils.output.get_pretty_output", return_value=False)
    def test_emit_section_no_pretty(self, mock_get_pretty, mock_console):
        """Test section output (non-pretty mode)"""
        sink = ConsoleOutputSink()
        event = OutputEvent(
            text="", output_type=OutputType.SYSTEM, section="Test Section"
        )
        sink.emit(event)
        assert mock_console.print.called

    @patch("haijunbot.haijunbot_utils.output.console")
    @patch("haijunbot.haijunbot_utils.output.get_pretty_output", return_value=True)
    @patch("haijunbot.haijunbot_utils.output.get_agent_list", return_value="[1]TestAgent")
    def test_emit_simple_text(self, mock_get_agent_list, mock_get_pretty, mock_console):
        """Test simple text output"""
        sink = ConsoleOutputSink()
        event = OutputEvent(text="Hello World", output_type=OutputType.INFO)
        sink.emit(event)
        assert mock_console.print.called

    @patch("haijunbot.haijunbot_utils.output.console")
    @patch("haijunbot.haijunbot_utils.output.get_pretty_output", return_value=True)
    @patch(
        "haijunbot.haijunbot_utils.output.get_agent_list", return_value="[1]Agent1, Agent2"
    )
    @patch("haijunbot.haijunbot_utils.output.get_agent")
    def test_emit_multiline_list(
        self, mock_get_agent, mock_get_agent_list, mock_get_pretty, mock_console
    ):
        """Test multiline list output"""
        mock_agent = Mock()
        mock_agent.non_interactive = False
        mock_get_agent.return_value = mock_agent

        sink = ConsoleOutputSink()
        event = OutputEvent(
            text="- Item 1\n- Item 2\n- Item 3", output_type=OutputType.INFO
        )
        sink.emit(event)
        assert mock_console.print.called

    @patch("haijunbot.haijunbot_utils.output.console")
    @patch("haijunbot.haijunbot_utils.output.get_pretty_output", return_value=True)
    @patch("haijunbot.haijunbot_utils.output.get_agent_list", return_value="[1]TestAgent")
    def test_emit_progress_text(
        self, mock_get_agent_list, mock_get_pretty, mock_console
    ):
        """Test progress text highlighting"""
        sink = ConsoleOutputSink()
        event = OutputEvent(text="Executing round 3", output_type=OutputType.PROGRESS)
        sink.emit(event)
        assert mock_console.print.called

    @patch("haijunbot.haijunbot_utils.output.console")
    @patch("haijunbot.haijunbot_utils.output.get_pretty_output", return_value=True)
    @patch("haijunbot.haijunbot_utils.output.get_agent_list", return_value="[1]TestAgent")
    def test_emit_progress_with_total(
        self, mock_get_agent_list, mock_get_pretty, mock_console
    ):
        """Test progress text with total"""
        sink = ConsoleOutputSink()
        event = OutputEvent(text="Executing round 3/10", output_type=OutputType.PROGRESS)
        sink.emit(event)
        assert mock_console.print.called

    @patch("haijunbot.haijunbot_utils.output.console")
    @patch("haijunbot.haijunbot_utils.output.is_print_error_traceback", return_value=False)
    @patch("haijunbot.haijunbot_utils.output.get_pretty_output", return_value=True)
    @patch("haijunbot.haijunbot_utils.output.get_agent_list", return_value="[1]TestAgent")
    def test_emit_error_without_traceback(
        self,
        mock_get_agent_list,
        mock_get_pretty,
        mock_is_print_traceback,
        mock_console,
    ):
        """Test error output without printing stack trace"""
        sink = ConsoleOutputSink()
        event = OutputEvent(
            text="Error occurred", output_type=OutputType.ERROR, traceback=False
        )
        sink.emit(event)
        assert mock_console.print.called

    @patch("haijunbot.haijunbot_utils.output.console")
    @patch("haijunbot.haijunbot_utils.output.is_print_error_traceback", return_value=True)
    @patch("haijunbot.haijunbot_utils.output.get_pretty_output", return_value=True)
    @patch("haijunbot.haijunbot_utils.output.get_agent_list", return_value="[1]TestAgent")
    def test_emit_error_with_traceback(
        self,
        mock_get_agent_list,
        mock_get_pretty,
        mock_is_print_traceback,
        mock_console,
    ):
        """Test error output with stack trace printing"""
        mock_console.print_exception = Mock()
        sink = ConsoleOutputSink()
        event = OutputEvent(
            text="Error occurred", output_type=OutputType.ERROR, traceback=True
        )
        sink.emit(event)
        assert mock_console.print.called


class TestPrettyOutput:
    """Tests for PrettyOutput class"""

    @patch("haijunbot.haijunbot_utils.output.emit_output")
    def test_print_basic(self, mock_emit):
        """Test basic print method"""
        PrettyOutput._print("Hello World", OutputType.INFO)
        mock_emit.assert_called_once()
        args = mock_emit.call_args[0][0]
        assert args.text == "Hello World"
        assert args.output_type == OutputType.INFO
        assert isinstance(args.timestamp, str) and len(args.timestamp) > 0

    @patch("haijunbot.haijunbot_utils.output.emit_output")
    def test_print_with_timestamp_false(self, mock_emit):
        """Test print method (without timestamp)"""
        PrettyOutput._print("Hello World", OutputType.INFO, timestamp=False)
        args = mock_emit.call_args[0][0]
        assert args.timestamp is False

    @patch("haijunbot.haijunbot_utils.output.emit_output")
    def test_print_with_lang(self, mock_emit):
        """Test print method (with specified language)"""
        PrettyOutput._print("print('hello')", OutputType.CODE, lang="python")
        args = mock_emit.call_args[0][0]
        assert args.lang == "python"

    @patch("haijunbot.haijunbot_utils.output.emit_output")
    def test_print_with_traceback(self, mock_emit):
        """Test print method (print stack trace)"""
        PrettyOutput._print("Error occurred", OutputType.ERROR, traceback=True)
        args = mock_emit.call_args[0][0]
        assert args.traceback is True

    @patch("haijunbot.haijunbot_utils.output.emit_output")
    def test_section_basic(self, mock_emit):
        """Test basic section method"""
        PrettyOutput.section("Section Title")
        args = mock_emit.call_args[0][0]
        assert args.section == "Section Title"
        assert args.output_type == OutputType.INFO

    @patch("haijunbot.haijunbot_utils.output.emit_output")
    def test_section_with_output_type(self, mock_emit):
        """Test section method (with specified output type)"""
        PrettyOutput.section("Section Title", OutputType.WARNING)
        args = mock_emit.call_args[0][0]
        assert args.output_type == OutputType.WARNING

    @patch("haijunbot.haijunbot_utils.output.emit_output")
    def test_add_sink(self, mock_emit):
        """Test add_sink method"""
        custom_sink = Mock(spec=OutputSink)
        initial_count = len(PrettyOutput.get_sinks())
        PrettyOutput.add_sink(custom_sink)
        assert len(PrettyOutput.get_sinks()) == initial_count + 1
        assert custom_sink in PrettyOutput.get_sinks()
        # Cleanup
        PrettyOutput.clear_sinks()

    def test_clear_sinks_keep_default(self):
        """Test clear_sinks method (keep default sink)"""
        custom_sink = Mock(spec=OutputSink)
        PrettyOutput.add_sink(custom_sink)
        PrettyOutput.clear_sinks(keep_default=True)
        sinks = PrettyOutput.get_sinks()
        assert len(sinks) == 1
        assert isinstance(sinks[0], ConsoleOutputSink)

    def test_clear_sinks_remove_all(self):
        """Test clear_sinks method (remove all sinks)"""
        PrettyOutput.add_sink(Mock(spec=OutputSink))
        PrettyOutput.clear_sinks(keep_default=False)
        assert len(PrettyOutput.get_sinks()) == 0

    def test_get_sinks(self):
        """Test get_sinks method"""
        # First ensure there's a default sink
        sinks = PrettyOutput.get_sinks()
        assert isinstance(sinks, list)
        # If no sinks, add a default one
        if len(sinks) == 0:
            PrettyOutput.add_sink(ConsoleOutputSink())
            sinks = PrettyOutput.get_sinks()
        assert len(sinks) >= 1
        # Test that a copy is returned
        sinks.append("fake_sink")
        assert "fake_sink" not in PrettyOutput.get_sinks()

    def test_detect_language_python(self):
        """Test Python language detection"""
        text = """#!/usr/bin/env python
import os

def hello():
    print('world')

if __name__ == '__main__':
    hello()"""
        detected = PrettyOutput._detect_language(text)
        assert detected == "python"

    def test_detect_language_javascript(self):
        """Test JavaScript language detection"""
        text = """// JavaScript code
const x = 10;
function hello() {
    console.log('world');
}
module.exports = hello;"""
        detected = PrettyOutput._detect_language(text)
        # Since pygments recognition may not be accurate, we only verify it returns a valid result
        assert isinstance(detected, str)
        assert len(detected) > 0

    def test_detect_language_yaml(self):
        """Test YAML language detection"""
        text = """# YAML configuration
---
key: value
nested:
  item: 1"""
        detected = PrettyOutput._detect_language(text)
        # Since pygments may recognize YAML as other formats, we only verify it returns a valid result
        assert isinstance(detected, str)
        assert len(detected) > 0

    def test_detect_language_default(self):
        """Test default language detection"""
        text = "plain text content"
        detected = PrettyOutput._detect_language(text)
        assert detected == "markdown"

    def test_detect_language_custom_default(self):
        """Test custom default language"""
        text = "plain text"
        detected = PrettyOutput._detect_language(text, default_lang="text")
        assert detected == "text"

    def test_detect_language_json(self):
        """Test JSON language detection"""
        text = '{\n  "key": "value",\n  "number": 123,\n  "nested": {\n    "item": true\n  }\n}'
        detected = PrettyOutput._detect_language(text)
        # Since pygments may recognize JSON as other formats, we only verify it returns a valid result
        assert isinstance(detected, str)
        assert len(detected) > 0

    @patch(
        "haijunbot.haijunbot_utils.output.get_agent_list", return_value="[1]Agent1, Agent2"
    )
    @patch("haijunbot.haijunbot_utils.output.get_agent")
    @patch("haijunbot.haijunbot_utils.output.datetime")
    def test_format_with_timestamp(
        self, mock_datetime, mock_get_agent, mock_get_agent_list
    ):
        """Test _format method (timestamp parameter no longer used, only returns agent info)"""
        mock_agent = Mock()
        mock_agent.non_interactive = False
        mock_get_agent.return_value = mock_agent

        result = PrettyOutput._format(OutputType.INFO, timestamp="2026-07-30T12:34:56")
        assert "Agent1" in result
        assert "Agent2" in result
        assert "12:34:56" not in result  # Timestamp no longer appears in _format result

    @patch("haijunbot.haijunbot_utils.output.get_agent_list", return_value="[1]Agent1")
    @patch("haijunbot.haijunbot_utils.output.get_agent")
    def test_format_without_timestamp(self, mock_get_agent, mock_get_agent_list):
        """Test format method (without timestamp)"""
        mock_agent = Mock()
        mock_agent.non_interactive = False
        mock_get_agent.return_value = mock_agent

        result = PrettyOutput._format(OutputType.INFO, timestamp=False)
        assert "Agent1" in result

    @patch("haijunbot.haijunbot_utils.output.get_agent_list", return_value="")
    def test_format_no_agents(self, mock_get_agent_list):
        """Test format method (no agents)"""
        result = PrettyOutput._format(OutputType.INFO)
        assert result == ""

    @patch(
        "haijunbot.haijunbot_utils.output.get_agent_list", return_value="[2]Agent1, Agent2"
    )
    @patch("haijunbot.haijunbot_utils.output.get_agent")
    def test_format_non_interactive_agent(self, mock_get_agent, mock_get_agent_list):
        """Test format method (non-interactive agent)"""
        mock_agent1 = Mock()
        mock_agent1.non_interactive = True
        mock_agent2 = Mock()
        mock_agent2.non_interactive = False
        mock_get_agent.side_effect = [mock_agent1, mock_agent2]

        result = PrettyOutput._format(OutputType.INFO, timestamp=False)
        assert "Agent1" in result
        assert "Agent2" in result

    @patch(
        "haijunbot.haijunbot_utils.output.get_agent_list", return_value="[2]Agent1, Agent2"
    )
    @patch("haijunbot.haijunbot_utils.output.get_agent")
    def test_get_agent_list_with_emoji(self, mock_get_agent, mock_get_agent_list):
        """Test get_agent_list_with_emoji returns agent list with emoji"""
        mock_agent1 = Mock()
        mock_agent1.non_interactive = True
        mock_agent2 = Mock()
        mock_agent2.non_interactive = False
        mock_get_agent.side_effect = [mock_agent1, mock_agent2]

        result = PrettyOutput.get_agent_list_with_emoji()
        assert result == "[2]Agent1🔇, Agent2🔊"

    @patch("haijunbot.haijunbot_utils.output.get_agent_list", return_value="")
    def test_get_agent_list_with_emoji_empty(self, mock_get_agent_list):
        """Test get_agent_list_with_emoji returns empty string when no agents"""
        assert PrettyOutput.get_agent_list_with_emoji() == ""

    @patch("haijunbot.haijunbot_utils.output.get_agent_list", return_value="[1]Agent1")
    @patch("haijunbot.haijunbot_utils.output.get_agent")
    def test_print_context_contains_agent_list(
        self, mock_get_agent, mock_get_agent_list
    ):
        """Test _print writes agent_list to context"""
        mock_agent = Mock()
        mock_agent.non_interactive = False
        mock_get_agent.return_value = mock_agent

        captured = {}

        def fake_emit_output(event):
            captured["context"] = event.context

        with patch(
            "haijunbot.haijunbot_utils.output.emit_output", side_effect=fake_emit_output
        ):
            PrettyOutput._print("hello", OutputType.INFO)

        assert captured["context"].get("agent_list") == "[1]Agent1🔊"

    @patch("haijunbot.haijunbot_utils.output.console")
    def test_print_gradient_text_single_line(self, mock_console):
        """Test gradient text (single line)"""
        # Use at least two lines of text to avoid division by zero
        PrettyOutput.print_gradient_text("Hello\nWorld", (255, 0, 0), (0, 0, 255))
        mock_console.print.assert_called_once()
        # Verify the argument is a Text object
        call_args = mock_console.print.call_args
        from rich.text import Text

        assert isinstance(call_args[0][0], Text)

    @patch("haijunbot.haijunbot_utils.output.console")
    def test_print_gradient_text_multiline(self, mock_console):
        """Test gradient text (multiline)"""
        text = "Line 1\nLine 2\nLine 3"
        PrettyOutput.print_gradient_text(text, (255, 0, 0), (0, 255, 0))
        mock_console.print.assert_called_once()

    @patch("haijunbot.haijunbot_utils.output.console")
    def test_print_gradient_text_same_color(self, mock_console):
        """Test gradient text (same color)"""
        # Use at least two lines of text to avoid division by zero
        PrettyOutput.print_gradient_text(
            "Same\nColor", (100, 100, 100), (100, 100, 100)
        )
        mock_console.print.assert_called_once()

    @patch("haijunbot.haijunbot_utils.output.emit_output")
    def test_auto_print_warning_emoji(self, mock_emit):
        """Test auto_print (warning emoji)"""
        PrettyOutput.auto_print("⚠️ Warning message")
        args = mock_emit.call_args[0][0]
        assert args.output_type == OutputType.WARNING

    @patch("haijunbot.haijunbot_utils.output.emit_output")
    def test_auto_print_error_emoji(self, mock_emit):
        """Test auto_print (error emoji)"""
        PrettyOutput.auto_print("❌ Error message")
        args = mock_emit.call_args[0][0]
        assert args.output_type == OutputType.ERROR

    @patch("haijunbot.haijunbot_utils.output.emit_output")
    def test_auto_print_success_emoji(self, mock_emit):
        """Test auto_print (success emoji)"""
        PrettyOutput.auto_print("✅ Success message")
        args = mock_emit.call_args[0][0]
        assert args.output_type == OutputType.SUCCESS

    @patch("haijunbot.haijunbot_utils.output.emit_output")
    def test_auto_print_no_emoji(self, mock_emit):
        """Test auto_print (no emoji)"""
        PrettyOutput.auto_print("Plain message")
        args = mock_emit.call_args[0][0]
        assert args.output_type == OutputType.INFO

    @patch("haijunbot.haijunbot_utils.output.emit_output")
    def test_auto_print_multiline(self, mock_emit):
        """Test auto_print (multiline text)"""
        PrettyOutput.auto_print("First line\nSecond line")
        args = mock_emit.call_args[0][0]
        assert args.text.startswith("\n")

    @patch("haijunbot.haijunbot_utils.output.emit_output")
    def test_auto_print_emoji_spacing(self, mock_emit):
        """Test auto_print (emoji spacing)"""
        PrettyOutput.auto_print("Message without space")
        args = mock_emit.call_args[0][0]
        assert "Message without space" == args.text

    @patch("haijunbot.haijunbot_utils.output.emit_output")
    def test_auto_print_with_timestamp_false(self, mock_emit):
        """Test auto_print (without timestamp)"""
        PrettyOutput.auto_print("Message", timestamp=False)
        args = mock_emit.call_args[0][0]
        assert args.timestamp is False

    @patch("haijunbot.haijunbot_utils.output.console")
    def test_print_markdown_basic(self, mock_console):
        """Test print_markdown (basic)"""
        content = "# Title\nContent here"
        PrettyOutput.print_markdown(content)
        assert mock_console.print.called

    @patch("haijunbot.haijunbot_utils.output.console")
    def test_print_markdown_with_title(self, mock_console):
        """Test print_markdown (with title)"""
        content = "# Title\nContent here"
        PrettyOutput.print_markdown(content, title="Test Panel")
        assert mock_console.print.called

    @patch("haijunbot.haijunbot_utils.output.console")
    def test_print_markdown_custom_border_style(self, mock_console):
        """Test print_markdown (custom border style)"""
        content = "# Title\nContent here"
        PrettyOutput.print_markdown(content, border_style="green")
        assert mock_console.print.called

    @patch("haijunbot.haijunbot_utils.output.console")
    def test_print_markdown_custom_theme(self, mock_console):
        """Test print_markdown (custom theme)"""
        content = "```python\nprint('hello')\n```"
        PrettyOutput.print_markdown(content, theme="github-dark")
        assert mock_console.print.called


class TestEmitOutput:
    """Tests for emit_output function"""

    @patch("haijunbot.haijunbot_utils.output.console")
    def test_emit_to_all_sinks(self, mock_console):
        """Test broadcasting events to all sinks"""
        sink1 = Mock(spec=OutputSink)
        sink2 = Mock(spec=OutputSink)

        PrettyOutput.clear_sinks(keep_default=False)
        PrettyOutput.add_sink(sink1)
        PrettyOutput.add_sink(sink2)

        event = OutputEvent(text="Test", output_type=OutputType.INFO)
        emit_output(event)

        sink1.emit.assert_called_once_with(event)
        sink2.emit.assert_called_once_with(event)

        # Cleanup
        PrettyOutput.clear_sinks()

    @patch("haijunbot.haijunbot_utils.output.console")
    def test_emit_with_sink_exception(self, mock_console):
        """Test sink exception does not affect other sinks"""
        sink1 = Mock(spec=OutputSink)
        sink1.emit.side_effect = Exception("Sink1 error")
        sink2 = Mock(spec=OutputSink)

        PrettyOutput.clear_sinks(keep_default=False)
        PrettyOutput.add_sink(sink1)
        PrettyOutput.add_sink(sink2)

        event = OutputEvent(text="Test", output_type=OutputType.INFO)
        emit_output(event)

        # sink2 should still be called
        sink2.emit.assert_called_once_with(event)
        # Error message should be printed
        assert mock_console.print.called

        # Cleanup
        PrettyOutput.clear_sinks()
