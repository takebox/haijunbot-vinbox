# -*- coding: utf-8 -*-
"""
Output formatting module
This module provides rich text formatting and display tools for the HaijunBot system.
Includes:
- OutputType enum for categorizing different output types
- PrettyOutput class for formatting and displaying styled output
- Syntax highlighting support for multiple programming languages
- Panel display for structured output
"""

from abc import ABC
from abc import abstractmethod
from dataclasses import dataclass
from enum import Enum
import re
from typing import Any
from typing import Callable
from typing import Dict
from typing import Generator
from typing import List
from typing import Literal
from typing import Optional
from typing import Tuple
from datetime import datetime
import threading

from pygments.lexers import guess_lexer
from pygments.util import ClassNotFound
from rich.style import Style as RichStyle
from rich.syntax import Syntax
from rich.text import Text

from haijunbot.haijunbot_utils.config import get_pretty_output
from haijunbot.haijunbot_utils.exception_utils import save_exception
from haijunbot.haijunbot_utils.config import is_print_error_traceback
from haijunbot.haijunbot_utils.globals import console
from haijunbot.haijunbot_utils.globals import get_agent_list
from haijunbot.haijunbot_utils.globals import get_agent


# List of standard colors supported by Rich
RICH_STANDARD_COLORS = {
    "black",
    "red",
    "green",
    "yellow",
    "blue",
    "magenta",
    "cyan",
    "white",
    "bright_black",
    "bright_red",
    "bright_green",
    "bright_yellow",
    "bright_blue",
    "bright_magenta",
    "bright_cyan",
    "bright_white",
    "dark_red",
    "dark_green",
    "dark_yellow",
    "dark_blue",
    "dark_magenta",
    "dark_cyan",
    "grey0",
    "grey100",
    "grey50",
    "grey70",
    "grey30",
}


def _safe_color_get(color_name: str, fallback: str = "white") -> str:
    """
    Safe color retrieval function that provides color validation and fallback mechanisms.

    Args:
        color_name: The desired color name
        fallback: Fallback color name (defaults to white)

    Returns:
        A valid color name; returns the fallback color if the original color is invalid
    """
    if color_name in RICH_STANDARD_COLORS:
        return color_name

    # Try some common color alias mappings
    color_alias_map = {
        "dark_olive_green": "green",
        "orange3": "bright_yellow",
        "sea_green3": "green",
        "dark_sea_green": "green",
        "grey58": "grey50",
    }

    return color_alias_map.get(color_name, fallback)


class OutputType(Enum):
    """
    Output type enum used to categorize and style different types of messages.

    Attributes:
        SYSTEM: AI assistant message
        CODE: Code-related output
        RESULT: Tool execution result
        ERROR: Error message
        INFO: System hint
        PLANNING: Task planning
        PROGRESS: Execution progress
        SUCCESS: Success message
        WARNING: Warning message
        DEBUG: Debug message
        USER: User input
        TOOL: Tool call
        START: Task start
        TARGET: Target task
        STOP: Task stop
        RETRY: Retry operation
        ROLLBACK: Rollback operation
        DIRECTORY: Directory-related
        STATISTICS: Statistics
    """

    SYSTEM = "SYSTEM"
    CODE = "CODE"
    RESULT = "RESULT"
    ERROR = "ERROR"
    INFO = "INFO"
    PLANNING = "PLANNING"
    PROGRESS = "PROGRESS"
    SUCCESS = "SUCCESS"
    WARNING = "WARNING"
    DEBUG = "DEBUG"
    USER = "USER"
    TOOL = "TOOL"
    START = "START"
    TARGET = "TARGET"
    STOP = "STOP"
    RETRY = "RETRY"
    ROLLBACK = "ROLLBACK"
    DIRECTORY = "DIRECTORY"
    STATISTICS = "STATISTICS"
    CHEAP_MODEL = "CHEAP_MODEL"
    NORMAL_MODEL = "NORMAL_MODEL"
    SMART_MODEL = "SMART_MODEL"
    # Streaming output types
    STREAM_START = "STREAM_START"
    STREAM_CHUNK = "STREAM_CHUNK"
    STREAM_END = "STREAM_END"
    # Diff visualization types
    DIFF = "DIFF"


# Output type icon mapping (unified icon definitions)
OUTPUT_ICONS = {
    OutputType.SYSTEM: "🤖",
    OutputType.CODE: "📝",
    OutputType.RESULT: "✨",
    OutputType.ERROR: "❌",
    OutputType.INFO: "ℹ️",
    OutputType.PLANNING: "📋",
    OutputType.PROGRESS: "⏳",
    OutputType.SUCCESS: "✅",
    OutputType.WARNING: "⚠️",
    OutputType.DEBUG: "🔍",
    OutputType.USER: "👤",
    OutputType.TOOL: "🔧",
    OutputType.START: "🚀",
    OutputType.TARGET: "🎯",
    OutputType.STOP: "🛑",
    OutputType.RETRY: "🔄",
    OutputType.ROLLBACK: "🔙",
    OutputType.DIRECTORY: "📁",
    OutputType.STATISTICS: "📊",
    OutputType.CHEAP_MODEL: "💰",
    OutputType.NORMAL_MODEL: "⭐",
    OutputType.SMART_MODEL: "🧠",
    OutputType.STREAM_START: "⏳",
    OutputType.STREAM_CHUNK: "▶️",
    OutputType.STREAM_END: "✅",
    OutputType.DIFF: "🔄",
}


# Reverse mapping from Emoji to output type (including aliases)
EMOJI_TO_OUTPUT_TYPE = {
    "🤖": OutputType.SYSTEM,
    "📝": OutputType.CODE,
    "✨": OutputType.RESULT,
    "❌": OutputType.ERROR,
    "ℹ️": OutputType.INFO,
    "📋": OutputType.PLANNING,
    "⏳": OutputType.PROGRESS,
    "✅": OutputType.SUCCESS,
    "⚠️": OutputType.WARNING,
    "🔍": OutputType.DEBUG,
    "👤": OutputType.USER,
    "🔧": OutputType.TOOL,
    "🚀": OutputType.START,
    "🎯": OutputType.TARGET,
    "🛑": OutputType.STOP,
    "🔄": OutputType.RETRY,
    "🔙": OutputType.ROLLBACK,
    "📁": OutputType.DIRECTORY,
    "📂": OutputType.DIRECTORY,  # alias
    "📊": OutputType.STATISTICS,
    "💰": OutputType.CHEAP_MODEL,
    "⭐": OutputType.NORMAL_MODEL,
    "🧠": OutputType.SMART_MODEL,
    "🎬": OutputType.STREAM_START,
    "▶️": OutputType.STREAM_CHUNK,
    "🏁": OutputType.STREAM_END,
}


@dataclass
class OutputEvent:
    """
    Common structure for output events, consumed by different output backends (Sinks).
    - text: Text content
    - output_type: Output type
    - timestamp: ISO-format time string (e.g. '2026-07-30T15:08:52'); None means no timestamp is shown
    - lang: Syntax highlighting language (optional; auto-detected if not provided)
    - traceback: Whether to display the exception traceback
    - section: If this is a section title output, fill in the title text; otherwise None
    - context: Extra context (reserved for TUI/logging, etc.)
    """

    text: str
    output_type: OutputType
    timestamp: Optional[str | bool] = None  # ISO-format time string
    lang: Optional[str] = None
    traceback: bool = False
    section: Optional[str] = None
    context: Optional[Dict[str, Any]] = None


def _get_timestamp() -> str:
    """Get the current time as an ISO-format timestamp string."""
    from datetime import datetime

    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


class OutputSink(ABC):
    """Abstract interface for output backends; different frontends (console/TUI/SSE/logging) implement this interface to consume output events."""

    @abstractmethod
    def emit(self, event: OutputEvent) -> None:  # pragma: no cover - abstract method
        raise NotImplementedError


class ConsoleOutputSink(OutputSink):
    """
    Default console output implementation, preserving the same behavior as the original PrettyOutput.
    """

    # Section style configuration (using unified icons)
    _SECTION_STYLES = {
        OutputType.SYSTEM: RichStyle(
            color="cyan", frame=True, meta={"icon": OUTPUT_ICONS[OutputType.SYSTEM]}
        ),
        OutputType.CODE: RichStyle(
            color="green", frame=True, meta={"icon": OUTPUT_ICONS[OutputType.CODE]}
        ),
        OutputType.RESULT: RichStyle(
            color="blue", frame=True, meta={"icon": OUTPUT_ICONS[OutputType.RESULT]}
        ),
        OutputType.ERROR: RichStyle(
            color="bright_red",
            frame=True,
            meta={"icon": OUTPUT_ICONS[OutputType.ERROR]},
            blink=True,
            bold=True,
        ),
        OutputType.INFO: RichStyle(
            color="grey70", frame=True, meta={"icon": OUTPUT_ICONS[OutputType.INFO]}
        ),
        OutputType.PLANNING: RichStyle(
            color="magenta",
            bold=True,
            frame=True,
            meta={"icon": OUTPUT_ICONS[OutputType.PLANNING]},
        ),
        OutputType.PROGRESS: RichStyle(
            color="grey50",
            encircle=True,
            frame=True,
            meta={"icon": OUTPUT_ICONS[OutputType.PROGRESS]},
        ),
        OutputType.SUCCESS: RichStyle(
            color="bright_green",
            bold=True,
            strike=False,
            meta={"icon": OUTPUT_ICONS[OutputType.SUCCESS]},
        ),
        OutputType.WARNING: RichStyle(
            color="bright_yellow",
            bold=True,
            blink=True,
            meta={"icon": OUTPUT_ICONS[OutputType.WARNING]},
        ),
        OutputType.DEBUG: RichStyle(
            color="grey50",
            dim=True,
            conceal=True,
            meta={"icon": OUTPUT_ICONS[OutputType.DEBUG]},
        ),
        OutputType.USER: RichStyle(
            color="bright_green",
            frame=True,
            meta={"icon": OUTPUT_ICONS[OutputType.USER]},
        ),
        OutputType.TOOL: RichStyle(
            color="green", frame=True, meta={"icon": OUTPUT_ICONS[OutputType.TOOL]}
        ),
        OutputType.START: RichStyle(
            color="bright_cyan",
            bold=True,
            frame=True,
            meta={"icon": OUTPUT_ICONS[OutputType.START]},
        ),
        OutputType.TARGET: RichStyle(
            color="bright_magenta",
            bold=True,
            frame=True,
            meta={"icon": OUTPUT_ICONS[OutputType.TARGET]},
        ),
        OutputType.STOP: RichStyle(
            color="bright_red",
            bold=True,
            frame=True,
            meta={"icon": OUTPUT_ICONS[OutputType.STOP]},
        ),
        OutputType.RETRY: RichStyle(
            color="grey70",
            bold=True,
            frame=True,
            meta={"icon": OUTPUT_ICONS[OutputType.RETRY]},
        ),
        OutputType.ROLLBACK: RichStyle(
            color="grey70",
            bold=True,
            frame=True,
            meta={"icon": OUTPUT_ICONS[OutputType.ROLLBACK]},
        ),
        OutputType.DIRECTORY: RichStyle(
            color="cyan", frame=True, meta={"icon": OUTPUT_ICONS[OutputType.DIRECTORY]}
        ),
        OutputType.STATISTICS: RichStyle(
            color="grey58",
            frame=True,
            meta={"icon": OUTPUT_ICONS[OutputType.STATISTICS]},
        ),
        OutputType.CHEAP_MODEL: RichStyle(
            color="grey58",
            frame=True,
            meta={"icon": OUTPUT_ICONS[OutputType.CHEAP_MODEL]},
        ),
        OutputType.NORMAL_MODEL: RichStyle(
            color="bright_blue",
            frame=True,
            meta={"icon": OUTPUT_ICONS[OutputType.NORMAL_MODEL]},
        ),
        OutputType.SMART_MODEL: RichStyle(
            color="bright_magenta",
            bold=True,
            frame=True,
            meta={"icon": OUTPUT_ICONS[OutputType.SMART_MODEL]},
        ),
        OutputType.DIFF: RichStyle(
            color="cyan",
            frame=True,
            meta={"icon": OUTPUT_ICONS[OutputType.DIFF]},
        ),
    }

    # Text color mapping
    _TEXT_COLORS = {
        OutputType.SYSTEM: "cyan",
        OutputType.CODE: "green",
        OutputType.RESULT: "blue",
        OutputType.ERROR: "bright_red",
        OutputType.INFO: "grey70",
        OutputType.PLANNING: "magenta",
        OutputType.PROGRESS: "grey50",
        OutputType.SUCCESS: "bright_green",
        OutputType.WARNING: "bright_yellow",
        OutputType.DEBUG: "grey30",
        OutputType.USER: "bright_green",
        OutputType.TOOL: "green",
        OutputType.START: "bright_cyan",
        OutputType.TARGET: "bright_magenta",
        OutputType.STOP: "bright_red",
        OutputType.RETRY: "grey70",
        OutputType.ROLLBACK: "grey70",
        OutputType.DIRECTORY: "cyan",
        OutputType.STATISTICS: "grey58",
        OutputType.CHEAP_MODEL: "grey58",
        OutputType.NORMAL_MODEL: "bright_blue",
        OutputType.SMART_MODEL: "bright_magenta",
        OutputType.DIFF: "cyan",
    }

    @staticmethod
    def _highlight_progress_text(
        text: str, output_type: OutputType, text_colors: Dict[OutputType, str]
    ) -> Text:
        """
        Detect and highlight progress information in the text (such as "round X" or "round X/Y").

        Args:
            text: The text to process
            output_type: Output type
            text_colors: Color mapping dictionary

        Returns:
            Text: The formatted text object
        """
        progress_pattern = r"round\s*(\d+)(?:/(\d+))?\s*"
        if re.search(progress_pattern, text):
            # Contains progress information, highlight the numbers
            parts = re.split(progress_pattern, text)
            colored_text = Text()
            for i, part in enumerate(parts):
                if i % 3 == 0:  # normal text
                    colored_text.append(
                        part,
                        style=RichStyle(
                            color=_safe_color_get(text_colors[output_type], "white")
                        ),
                    )
                elif i % 3 == 1:  # first number (current round)
                    colored_text.append(
                        part,
                        style=RichStyle(
                            color=_safe_color_get(text_colors[output_type], "white"),
                            bold=True,
                        ),
                    )
                elif i % 3 == 2 and part:  # second number (total rounds, if any)
                    colored_text.append(
                        f"/{part}",
                        style=RichStyle(
                            color=_safe_color_get(text_colors[output_type], "white")
                        ),
                    )
            return colored_text
        else:
            # normal text
            return Text(
                text,
                style=RichStyle(
                    color=_safe_color_get(text_colors[output_type], "white")
                ),
            )

    def emit(self, event: OutputEvent) -> None:
        # Streaming output types are handled by the Gateway; ignored in CLI mode
        if event.output_type in (
            OutputType.STREAM_START,
            OutputType.STREAM_CHUNK,
            OutputType.STREAM_END,
        ):
            return

        # Section output
        if event.section is not None:
            # Use Text with background color and style instead of Panel
            style_obj = self._SECTION_STYLES.get(
                event.output_type, RichStyle(color="white")
            )
            text = Text(f"\n{event.section}\n", style=style_obj, justify="center")
            if get_pretty_output():
                console.print(text)
            else:
                console.print(Text(event.section, style=event.output_type.value))
            return

        # Normal content output
        lang = (
            event.lang
            if event.lang is not None
            else PrettyOutput._detect_language(event.text, default_lang="markdown")
        )

        content = Syntax(
            event.text,
            lang,
            theme="monokai",
            word_wrap=True,
            # Use the terminal's default background color
        )
        # Output content with background color directly, no longer wrapped in Panel
        agent_name = PrettyOutput._format(event.output_type, event.timestamp)
        header_text = Text(
            agent_name,
            style=RichStyle(color="grey58", dim=True),
        )
        if get_pretty_output():
            # Detect whether this is multi-line text; if so, use better formatting
            lines = event.text.split("\n")
            is_multiline = len(lines) > 1

            # Detect whether it contains list items (starting with a number, -, *)
            is_list = any(
                line.strip().startswith(("- ", "* ", "• "))
                or (
                    line.strip()
                    and line.strip()[0].isdigit()
                    and ". " in line.strip()[:5]
                )
                for line in lines
            )

            # Detect whether it contains indented content (possibly sub-items or code blocks)
            has_indent = any(line.startswith(("   ", "  ", "\t")) for line in lines)

            if is_multiline and (is_list or has_indent):
                # Multi-line list or indented content: the first line shows the header, subsequent lines use indentation
                combined_text = Text()
                combined_text.append(header_text)
                combined_text.append(" ")

                # First line: detect and highlight progress information
                first_line = lines[0]
                colored_first_line = self._highlight_progress_text(
                    first_line, event.output_type, self._TEXT_COLORS
                )

                combined_text.append(colored_first_line)
                console.print(combined_text)

                # Subsequent lines use indentation to maintain visual hierarchy
                for line in lines[1:]:
                    if line.strip():  # non-empty line
                        # Detect list item markers and format appropriately
                        line_stripped = line.strip()
                        is_list_item = line_stripped.startswith(("- ", "* ", "• ")) or (
                            line_stripped
                            and line_stripped[0].isdigit()
                            and ". " in line_stripped[:5]
                        )

                        # If already indented, keep as is; otherwise add indentation
                        if line.startswith(("   ", "  ", "\t")):
                            display_line = line
                        else:
                            display_line = f"   {line}"

                        indented_line = Text(
                            display_line,
                            style=RichStyle(
                                color=_safe_color_get(
                                    self._TEXT_COLORS[event.output_type], "white"
                                ),
                                dim=not is_list_item
                                and line.startswith(
                                    ("   ", "  ", "\t")
                                ),  # already-indented non-list items are slightly dimmed
                            ),
                        )
                        console.print(indented_line)
                    else:
                        console.print()  # empty line kept as is
            else:
                # Single line or simple multi-line: merge header and content and display on the same line
                combined_text = Text()
                combined_text.append(header_text)
                combined_text.append(" ")

                # Detect and highlight progress information (single-line case)
                colored_content = self._highlight_progress_text(
                    event.text, event.output_type, self._TEXT_COLORS
                )
                combined_text.append(colored_content)

                console.print(combined_text)
        else:
            console.print(content)
        if event.traceback or (
            event.output_type == OutputType.ERROR and is_print_error_traceback()
        ):
            try:
                console.print_exception()
            except Exception as e:
                console.print(f"Error: {e}")


# Module-level output dispatcher (registers the console backend by default)
_output_sinks: List[OutputSink] = [ConsoleOutputSink()]

# Output lock to ensure multi-threaded output does not get garbled
_output_lock = threading.Lock()


def emit_output(event: OutputEvent) -> None:
    """Broadcast the event to all registered output backends."""
    # First check whether console output should be skipped (to avoid printing Gateway-specific data to the terminal)
    context = event.context or {}
    skip_console = context.get("_gateway_skip", False)

    # In quiet mode, suppress console output but still keep gateway/event output
    if not skip_console:
        try:
            from haijunbot.haijunbot_utils.config import is_quiet

            if is_quiet():
                skip_console = True
        except Exception:
            pass

    # If the skip flag is not set, broadcast the event to all output backends
    if not skip_console:
        with _output_lock:
            for sink in list(_output_sinks):
                try:
                    sink.emit(event)
                except Exception as e:
                    # A backend failure does not affect other backends
                    console.print(f"[Output backend error] {sink.__class__.__name__}: {e}")

    try:
        from haijunbot.haijunbot_gateway.events import GatewayOutputEvent
        from haijunbot.haijunbot_gateway.manager import get_current_gateway
    except Exception:
        return

    gateway = get_current_gateway()
    if gateway is None:
        return

    gateway_context = dict(context) if context else {}
    if not gateway_context.get("agent_id"):
        try:
            from haijunbot.haijunbot_utils import globals as jglobals

            if jglobals.agent_id:
                gateway_context["agent_id"] = jglobals.agent_id
        except Exception as e:
            save_exception(e, module="haijunbot_utils.output", function="emit_output")
            pass
    gateway_context.pop("_gateway_skip", None)
    if not gateway_context:
        gateway_context = None

    try:
        gateway.emit_output(
            GatewayOutputEvent(
                text=event.text,
                output_type=event.output_type.value,
                timestamp=event.timestamp,
                lang=event.lang,
                traceback=event.traceback,
                section=event.section,
                context=gateway_context,
            )
        )
    except Exception as e:
        console.print(f"[Gateway output error] {gateway.__class__.__name__}: {e}")


class PrettyOutput:
    """
    A class that uses the rich library to format and display rich text output.

    Provides the following methods:
    - Format different types of output using appropriate styles
    - Syntax highlighting for code blocks
    - Panel display for structured content
    - Progressively displayed streaming output
    """

    # Language mapping for syntax highlighting
    _lang_map = {
        "Python": "python",
        "JavaScript": "javascript",
        "TypeScript": "typescript",
        "Java": "java",
        "C++": "cpp",
        "C#": "csharp",
        "Ruby": "ruby",
        "PHP": "php",
        "Go": "go",
        "Rust": "rust",
        "Bash": "bash",
        "HTML": "html",
        "CSS": "css",
        "SQL": "sql",
        "R": "r",
        "Kotlin": "kotlin",
        "Swift": "swift",
        "Scala": "scala",
        "Perl": "perl",
        "Lua": "lua",
        "YAML": "yaml",
        "JSON": "json",
        "XML": "xml",
        "Markdown": "markdown",
        "Text": "text",
        "Shell": "bash",
        "Dockerfile": "dockerfile",
        "Makefile": "makefile",
        "INI": "ini",
        "TOML": "toml",
    }

    @staticmethod
    def _detect_language(text: str, default_lang: str = "markdown") -> str:
        """
        Detect the programming language of the given text.

        Args:
            text: The text to analyze
            default_lang: The language to return by default if detection fails

        Returns:
            str: The detected language name
        """
        try:
            lexer = guess_lexer(text)
            detected_lang = lexer.name
            return PrettyOutput._lang_map.get(detected_lang, default_lang)
        except (ClassNotFound, Exception):
            return default_lang

    @staticmethod
    def get_agent_list_with_emoji() -> str:
        """
        Get the Agent list string with interaction-status emojis.

        Returns:
            str: A string like "[2]name1🔊, name2🔇"; returns an empty string when there are no Agents
        """
        agent_info = get_agent_list()
        if not agent_info:
            return ""

        # Extract the list of agent names (removing the leading count marker)
        match = re.match(r"^\[(\d+)\](.+)$", agent_info)
        if match:
            count = match.group(1)
            agent_names = match.group(2).strip()
            # Add the corresponding emoji to each agent name (based on its non_interactive status)
            agent_names_with_emoji = []
            for name in agent_names.split(", "):
                name = name.strip()
                agent = get_agent(name)
                if agent and getattr(agent, "non_interactive", False):
                    emoji = "🔇"  # non-interactive mode
                else:
                    emoji = "🔊"  # interactive mode
                agent_names_with_emoji.append(f"{name}{emoji}")
            agent_info = f"[{count}]{', '.join(agent_names_with_emoji)}"

        return agent_info

    @staticmethod
    def _format(output_type: OutputType, timestamp: Optional[str | bool] = None) -> str:
        """
        Return the Agent name format (the timestamp is displayed by the frontend).

        Args:
            output_type: Output type (no longer used)
            timestamp: ISO-format time string (kept for parameter compatibility, but no longer used)

        Returns:
            str: The Agent name string
        """
        return PrettyOutput.get_agent_list_with_emoji()

    @staticmethod
    def _print(
        text: str,
        output_type: OutputType,
        timestamp: Optional[str | bool] = None,
        lang: Optional[str] = None,
        traceback: bool = False,
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Print formatted output using styles and syntax highlighting (now abstracted as an event + Sink mechanism).
        Internal interface; not recommended for direct use, please use auto_print instead.
        Maintains backward compatibility with existing callers while reserving extension points for frontends such as TUI/logging.

        Args:
            timestamp: ISO-format time string; None means automatically generate the current timestamp
        """
        # Automatically obtain context information
        if context is None:
            context = {}

        # Get the current agent name
        try:
            from haijunbot.haijunbot_utils.globals import get_current_agent_name

            agent_name = get_current_agent_name()
            if agent_name and "agent_name" not in context:
                context["agent_name"] = agent_name
        except Exception as e:
            save_exception(e, module="haijunbot_utils.output", function="_print")
            pass

        # Get the current ARCHER workflow stage
        try:
            from haijunbot.haijunbot_utils.globals import get_current_agent

            agent = get_current_agent()
            if agent and hasattr(agent, "state_manager"):
                current_mode = agent.state_manager.get_mode()
                if current_mode and "current_mode" not in context:
                    context["current_mode"] = current_mode
        except Exception as e:
            save_exception(e, module="haijunbot_utils.output", function="_print")
            pass

        # Get whether it is in non-interactive mode
        try:
            from haijunbot.haijunbot_utils.config import is_non_interactive

            non_interactive = is_non_interactive()
            if "non_interactive" not in context:
                context["non_interactive"] = non_interactive
        except Exception as e:
            save_exception(e, module="haijunbot_utils.output", function="_print")
            pass

        # Get the agent chain list within the current process (with interaction-status emojis)
        try:
            if "agent_list" not in context:
                context["agent_list"] = PrettyOutput.get_agent_list_with_emoji()
        except Exception as e:
            save_exception(e, module="haijunbot_utils.output", function="_print")
            pass

        # Generate the timestamp: if not provided, automatically generate the current time in ISO format
        from datetime import datetime

        actual_timestamp = (
            timestamp
            if timestamp is not None
            else datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        )

        event = OutputEvent(
            text=text,
            output_type=output_type,
            timestamp=actual_timestamp,
            lang=lang,
            traceback=traceback,
            context=context if context else None,
        )
        emit_output(event)

    @staticmethod
    def section(title: str, output_type: OutputType = OutputType.INFO) -> None:
        """
        Print a section title in a styled panel (dispatched via the event + Sink mechanism).
        """
        event = OutputEvent(
            text="",
            output_type=output_type,
            section=title,
            timestamp=_get_timestamp(),
        )
        emit_output(event)

    @staticmethod
    # Sink management (reserved for externally registering custom backends)
    @staticmethod
    def add_sink(sink: OutputSink) -> None:
        """Register a new output backend."""
        with _output_lock:
            _output_sinks.append(sink)

    @staticmethod
    def remove_sink(sink: OutputSink) -> None:
        """Remove the specified output backend; ignore it if it does not exist."""
        with _output_lock:
            try:
                _output_sinks.remove(sink)
            except ValueError:
                pass

    @staticmethod
    def clear_sinks(keep_default: bool = True) -> None:
        """Clear the registered output backends; optionally keep the default console backend."""
        with _output_lock:
            if keep_default:
                globals()["_output_sinks"] = [
                    s for s in _output_sinks if isinstance(s, ConsoleOutputSink)
                ]
            else:
                _output_sinks.clear()

    @staticmethod
    def get_sinks() -> List[OutputSink]:
        """Get the list of currently registered output backends (a copy)."""
        return list(_output_sinks)

    @staticmethod
    def print_gradient_text(
        text: str, start_color: Tuple[int, int, int], end_color: Tuple[int, int, int]
    ) -> None:
        """Print text with gradient colors.

        Args:
            text: The text to print
            start_color: Starting RGB color tuple (r, g, b)
            end_color: Ending RGB color tuple (r, g, b)
        """
        lines = text.strip("\n").split("\n")
        total_lines = len(lines)
        colored_lines = []
        for i, line in enumerate(lines):
            # Calculate the gradient color for the current line
            r = int(
                start_color[0] + (end_color[0] - start_color[0]) * i / (total_lines - 1)
            )
            g = int(
                start_color[1] + (end_color[1] - start_color[1]) * i / (total_lines - 1)
            )
            b = int(
                start_color[2] + (end_color[2] - start_color[2]) * i / (total_lines - 1)
            )

            # Set color using ANSI escape sequences
            colored_lines.append(f"\033[38;2;{r};{g};{b}m{line}\033[0m")
        colored_text = Text(
            "\n".join(colored_lines), style=OutputType.TOOL.value, justify="center"
        )
        # Output gradient text directly, no longer wrapped in Panel
        console.print(colored_text)

    @staticmethod
    def auto_print(
        text: str,
        timestamp: Optional[str | bool] = None,
        lang: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Automatically determine the type based on the prefix emoji of the printed message and output it colored.

        Supported emoji prefix mappings:
        - ⚠️ -> WARNING (yellow warning)
        - ❌ -> ERROR (red error)
        - ✅ -> SUCCESS (green success)
        - ℹ️ -> INFO (cyan info)
        - 📋 -> PLANNING (purple planning)
        - ⏳ -> PROGRESS (white progress)
        - 🔍 -> DEBUG (gray debug)
        - 🤖 -> SYSTEM (cyan system)
        - 📝 -> CODE (green code)
        - ✨ -> RESULT (blue result)
        - 👤 -> USER (green user)
        - 🔧 -> TOOL (green tool)

        Parameters:
            text: the text to print
            timestamp: whether to display the timestamp
            lang: language type (for syntax highlighting)
            context: extra context info (used by the frontend to display agent_name, etc.)
        """
        # Detect emoji prefix (using the unified emoji mapping)
        output_type = OutputType.INFO  # default type
        detected_emoji = None
        for emoji, type_enum in EMOJI_TO_OUTPUT_TYPE.items():
            if text.startswith(emoji):
                output_type = type_enum
                detected_emoji = emoji
                break

        # Optimize text format: ensure proper spacing between emoji and text
        if detected_emoji:
            # If there is no space after the emoji, add one
            if len(text) > len(detected_emoji) and text[len(detected_emoji)] != " ":
                text = f"{detected_emoji} {text[len(detected_emoji) :].lstrip()}"

        # If the content to print contains newlines, add a newline at the start of the content to print
        if "\n" in text:
            text = f"\n{text}"

        # If there is current stage info, add a stage marker before the text
        if context and "current_mode" in context:
            mode = context["current_mode"]
            text = f"[{mode}] {text}"

        # Use the existing print method for colored output
        PrettyOutput._print(
            text=text,
            output_type=output_type,
            timestamp=timestamp,
            lang=lang,
            context=context,
        )

    @staticmethod
    def _left_aligned_heading_rich_console(
        self: Any, rich_console: Any, options: Any
    ) -> Any:
        """Custom Rich Markdown Heading rendering to left-align headings."""
        from rich import box
        from rich.panel import Panel
        from rich.text import Text

        text = self.text
        text.justify = "left"
        if self.tag == "h1":
            yield Panel(
                text,
                box=box.HORIZONTALS,
                style="markdown.h1.border",
            )
        else:
            if self.tag == "h2":
                yield Text("")
            yield text

    @staticmethod
    def print_markdown(
        content: str,
        title: Optional[str] = None,
        border_style: str = "bright_blue",
        theme: str = "monokai",
    ) -> None:
        """
        Display content with Markdown rendering using a Panel (headings left-aligned).

        Parameters:
            content: the markdown-formatted content to display
            title: Panel title (optional)
            border_style: border style (default "bright_blue")
            theme: markdown highlight theme (default "monokai")
        """
        if not content.strip():
            return
        from rich import box
        from rich.markdown import Markdown, Heading
        from rich.panel import Panel

        # Save the original method
        _original_rich_console = Heading.__rich_console__

        # Temporarily apply the patch
        setattr(
            Heading, "__rich_console__", PrettyOutput._left_aligned_heading_rich_console
        )

        try:
            # Create the Markdown render object
            markdown = Markdown(content, code_theme=theme)

            # Create a Panel wrapping the Markdown object
            panel = Panel(
                markdown,
                title=title,
                border_style=border_style,
                box=box.HORIZONTALS,
                expand=True,
            )

            # Print the Panel to the terminal
            console.print(panel)
        finally:
            # Restore the original method
            setattr(Heading, "__rich_console__", _original_rich_console)

        # Output to Gateway via the event system (for the Web interface)
        # Note: only send events in Gateway mode to avoid duplicate printing in CLI mode
        try:
            from haijunbot.haijunbot_gateway.manager import get_current_gateway
        except Exception:
            return

        if get_current_gateway() is not None:
            event = OutputEvent(
                text=content,
                output_type=OutputType.RESULT,
                lang="markdown",
                section=title,
                timestamp=_get_timestamp(),
            )
            emit_output(event)

    @staticmethod
    def print_centered_panel(
        renderable: Any,
        title: Optional[str] = None,
        title_align: Literal["left", "center", "right"] = "center",
        border_style: str = "blue",
        **kwargs: Any,
    ) -> None:
        """
        Display content using a centered Panel.

        Parameters:
            renderable: the content to display (Text, Group, and other Rich renderables)
            title: Panel title (optional)
            title_align: title alignment (default "center")
            border_style: border style (default "blue")
            **kwargs: other arguments passed to Panel
        """
        from rich import box
        from rich.align import Align
        from rich.panel import Panel

        panel = Panel(
            renderable,
            title=title,
            title_align=title_align,
            border_style=border_style,
            box=box.HORIZONTALS,
            **kwargs,
        )
        console.print(Align.center(panel))

    @staticmethod
    def print_script_panel(
        content: str,
        title: str,
        lang: str = "python",
        theme: str = "monokai",
    ) -> None:
        """
        Display script content with syntax highlighting using a Panel.

        Parameters:
            content: script content
            title: Panel title
            lang: syntax highlighting language (default "python")
            theme: highlight theme (default "monokai")
        """
        from rich import box
        from rich.panel import Panel

        syntax = Syntax(
            content,
            lang,
            theme=theme,
            line_numbers=True,
            word_wrap=True,
        )
        panel = Panel(syntax, title=title, border_style="cyan", box=box.HORIZONTALS)
        console.print(panel)

        # Output to Gateway via the event system (for the Web interface)
        # Note: only send events in Gateway mode to avoid duplicate printing in CLI mode
        try:
            from haijunbot.haijunbot_gateway.manager import get_current_gateway
        except Exception:
            return

        if get_current_gateway() is not None:
            event = OutputEvent(
                text=content,
                output_type=OutputType.CODE,
                lang=lang,
                section=None,
                timestamp=_get_timestamp(),
            )
            emit_output(event)

    @staticmethod
    def print_resource_overview_panel(
        welcome_message: str,
        current_dir: str,
        stats_parts: List[str],
    ) -> None:
        """
        Display the HaijunBot resource overview panel (centered).

        Parameters:
            welcome_message: welcome message
            current_dir: current working directory
            stats_parts: list of statistics info (each item is a markup string)
        """
        stats_text = Text.from_markup(" | ".join(stats_parts), justify="center")
        panel_content = Text()
        panel_content.append(welcome_message, style="bold white")
        panel_content.append("\n")
        panel_content.append(f"📁  Working directory: {current_dir}", style="dim white")
        panel_content.append("\n\n")
        panel_content.append(stats_text)
        panel_content.justify = "center"
        PrettyOutput.print_centered_panel(
            panel_content,
            title="✨ HaijunBot Resource Overview ✨",
            title_align="center",
            border_style="blue",
            expand=False,
        )

    @staticmethod
    def print_welcome_panel(content: Any) -> None:
        """
        Display the welcome message panel (centered).

        Parameters:
            content: welcome content (Group, Text, and other Rich renderables)
        """
        from rich.align import Align
        from rich.panel import Panel

        terminal_width = console.width
        content_width = max(len(str(line)) for line in str(content).split("\n"))
        panel_width = max(terminal_width * 2 // 3, content_width)
        welcome_panel = Panel(
            content,
            border_style="cyan",
            expand=False,
            width=panel_width,
        )
        console.print(Align.center(welcome_panel))

    @staticmethod
    def stream_chat_with_panel(
        chat_iterator: Generator[Tuple[str, str], None, None],
        title: str,
        status_message: str,
        get_used_token_count: Callable[[], int],
        get_conversation_turn: Callable[[], int],
        get_platform_max_input_token_count: Callable[[], int],
        get_context_token_count: Callable[[str], int],
        append_session_history: Callable[[str, str], None],
        start_time: float,
        message: str = "",
        max_output: int = 0,
        check_interrupt: Callable[[], bool] = lambda: False,
        panel_lock: Optional[threading.RLock] = None,
        raise_on_error: bool = False,
    ) -> Tuple[str, str, float]:
        """
        Use Live+Panel for streaming chat output (pretty output mode).

        Parameters:
            chat_iterator: chat response iterator
            title: panel title (model name)
            status_message: Status message shown while waiting for the first token
            get_used_token_count: callback to get the number of used tokens
            get_conversation_turn: callback to get the conversation turn
            get_platform_max_input_token_count: callback to get the platform max token count
            get_context_token_count: callback to compute the token count of text
            append_session_history: callback to append session history
            start_time: start timestamp
            message: user message (used to save history on interrupt)
            max_output: maximum output length, 0 means unlimited
            check_interrupt: callback to check whether an interrupt is requested
            panel_lock: thread lock used to protect panel updates (optional)
            raise_on_error: whether to re-raise exceptions during streaming (default False,
                keeping the existing behavior of "print the error and return the collected content")

        Returns:
            Tuple[str, str, float]: (model response, reasoning content, first token time)
        """
        import time

        from rich import box
        from rich.live import Live
        from rich.panel import Panel
        from rich.status import Status

        from haijunbot.haijunbot_utils.config import get_conversation_turn_threshold
        from haijunbot.haijunbot_utils.config import is_immediate_abort
        from haijunbot.haijunbot_utils.utils import is_repeating_text

        first_chunk = None
        first_token_time = 0.0

        with Status(
            status_message,
            spinner="dots",
            console=console,
        ):
            try:
                while True:
                    if is_immediate_abort() and check_interrupt():
                        append_session_history(message, "")
                        return "", "", 0.0
                    first_chunk = next(chat_iterator)
                    if first_chunk and first_chunk[1]:  # check that content is not empty
                        first_token_time = time.time() - start_time
                        break
            except StopIteration:
                append_session_history(message, "")
                return "", "", 0.0
            except Exception:
                if raise_on_error:
                    raise
                append_session_history(message, "")
                return "", "", 0.0

        _lock = panel_lock if panel_lock is not None else threading.RLock()

        def _format_progress_bar(percent: float, width: int = 15) -> str:
            percent = max(0, min(100, percent))
            filled = int(width * percent / 100)
            empty = width - filled
            return "█" * filled + "░" * empty

        def _get_token_usage_info(current_response: str) -> Tuple[float, str, str]:
            try:
                history_tokens = get_used_token_count()
                current_response_tokens = get_context_token_count(current_response)
                total_tokens = history_tokens + current_response_tokens
                max_tokens = get_platform_max_input_token_count()
                if max_tokens > 0:
                    usage_percent = (total_tokens / max_tokens) * 100
                    percent_color = (
                        "red"
                        if usage_percent >= 90
                        else "yellow"
                        if usage_percent >= 80
                        else "green"
                    )
                    progress_bar = _format_progress_bar(usage_percent, width=15)
                    return usage_percent, percent_color, progress_bar
                return 0.0, "green", ""
            except Exception:
                return 0.0, "green", ""

        def _update_panel_subtitle(
            pnl: Panel,
            response: str,
            reasoning_content: str,
            is_completed: bool = False,
            duration: float = 0.0,
            first_tok_time: float = 0.0,
        ) -> None:
            current_time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            threshold = get_conversation_turn_threshold()
            try:
                usage_percent, percent_color, progress_bar = _get_token_usage_info(
                    response
                )
                max_tokens = get_platform_max_input_token_count()
                total_tokens = get_used_token_count() + get_context_token_count(
                    response
                )
                if is_completed:
                    response_tokens = get_context_token_count(
                        response
                    ) + get_context_token_count(reasoning_content)
                    generation_time = (
                        duration - first_tok_time
                        if duration > first_tok_time
                        else duration
                    )
                    tokens_per_second = (
                        response_tokens / generation_time if generation_time > 0 else 0
                    )
                    if max_tokens > 0 and progress_bar:
                        pnl.subtitle = (
                            f"[bold green]✓ {current_time_str} | ({get_conversation_turn()}/{threshold}) | Conversation completed in: {duration:.2f}s | "
                            f"first token: {first_tok_time:.2f}s | speed: {tokens_per_second:.1f} tokens/s | "
                            f"Token: [{percent_color}]{progress_bar} {usage_percent:.1f}% ({total_tokens}/{max_tokens})[/{percent_color}][/bold green]"
                        )
                    else:
                        pnl.subtitle = (
                            f"[bold green]✓ {current_time_str} | ({get_conversation_turn()}/{threshold}) | Conversation completed in: {duration:.2f}s | "
                            f"first token: {first_tok_time:.2f}s | speed: {tokens_per_second:.1f} tokens/s | "
                            f"Token: {total_tokens}/{max_tokens}[/bold green]"
                        )
                else:
                    if max_tokens > 0 and progress_bar:
                        pnl.subtitle = (
                            f"[yellow]{current_time_str} | ({get_conversation_turn()}/{threshold}) | Answering... (press Ctrl+C to interrupt) | "
                            f"Token: [{percent_color}]{progress_bar} {usage_percent:.1f}% ({total_tokens}/{max_tokens})[/{percent_color}][/yellow]"
                        )
                    else:
                        pnl.subtitle = f"[yellow]{current_time_str} | ({get_conversation_turn()}/{threshold}) | Answering... (press Ctrl+C to interrupt)[/yellow]"
            except Exception:
                if is_completed:
                    pnl.subtitle = f"[bold green]✓ {current_time_str} | ({get_conversation_turn()}/{threshold}) | Conversation completed in: {duration:.2f}s[/bold green]"
                else:
                    pnl.subtitle = f"[yellow]{current_time_str} | ({get_conversation_turn()}/{threshold}) | Answering... (press Ctrl+C to interrupt)[/yellow]"

        from rich.markdown import Markdown, Heading

        _original_rich_console = Heading.__rich_console__
        setattr(
            Heading, "__rich_console__", PrettyOutput._left_aligned_heading_rich_console
        )

        panel = Panel(
            Markdown("", code_theme="monokai"),
            title=f"[bold cyan]{title}[/bold cyan]",
            subtitle="[yellow]Answering... (press Ctrl+C to interrupt)[/yellow]",
            border_style="cyan",
            box=box.HORIZONTALS,
            expand=True,
        )

        response = ""
        reasoning_content = ""
        last_subtitle_update_time = time.time()
        subtitle_update_interval = 1
        update_count = 0
        last_repeating_check_len = 0
        repeating_check_interval = 100

        with Live(panel, refresh_per_second=6, transient=True) as live:

            def _update_panel_content(
                content: str,
                style: str = "bright_white",
                update_subtitle: bool = False,
                show_cursor: bool = True,
            ):
                nonlocal response, last_subtitle_update_time, update_count, panel

                update_count += 1

                # Render the accumulated response text with Markdown
                display_text = response
                # Add a dynamic cursor effect
                if show_cursor and content:
                    display_text = response + " ▌"

                # First create the Markdown object
                md_content = Markdown(display_text, code_theme="monokai")

                # Truncate text during streaming output to keep the Panel within the terminal's visible range
                # Compute based on the actual number of lines after Markdown rendering, not the original text line count
                if show_cursor:
                    max_text_height = console.height - 5
                    if max_text_height <= 0:
                        max_text_height = 1
                    # Use console.render_lines() to get the actual rendered line count
                    try:
                        rendered_lines = console.render_lines(
                            md_content, console.options
                        )
                        rendered_height = len(rendered_lines)
                        if rendered_height > max_text_height:
                            # Truncation needed: take backwards from the end of the original text and re-render
                            # Use a heuristic: estimate the content to keep proportionally by character count
                            ratio = max_text_height / rendered_height
                            estimated_chars = int(len(display_text) * ratio)
                            # Take from the end backwards, keeping the trailing content
                            truncated_text = display_text[-estimated_chars:]
                            # Ensure starting from a complete line (find the first newline)
                            newline_idx = truncated_text.find("\n")
                            if newline_idx != -1:
                                truncated_text = truncated_text[newline_idx + 1 :]
                            # Re-create the Markdown object
                            md_content = Markdown(truncated_text, code_theme="monokai")
                    except Exception:
                        # If rendering fails, fall back to the original line-based truncation logic
                        lines = display_text.split("\n")
                        if len(lines) > max_text_height:
                            display_text = "\n".join(lines[-max_text_height:])
                        # Re-create the Markdown object regardless, to ensure safety
                        md_content = Markdown(display_text, code_theme="monokai")

                with _lock:
                    # Directly update the panel's internal content
                    panel.renderable = md_content

                    current_time = time.time()
                    should_update_subtitle = (
                        update_subtitle
                        or update_count % 10 == 0
                        or (current_time - last_subtitle_update_time)
                        >= subtitle_update_interval
                    )

                    if should_update_subtitle:
                        _update_panel_subtitle(
                            panel, response, reasoning_content, is_completed=False
                        )
                        last_subtitle_update_time = current_time

                    try:
                        live.update(panel)
                    except (IndexError, RuntimeError):
                        pass

            # Unpack the tuple (chunk_type, chunk_content)
            first_chunk_type, first_chunk_content = first_chunk
            # Only content type is appended to response
            if first_chunk_type == "content":
                response += first_chunk_content
            if first_chunk_content:
                # Set the style based on the type
                first_style = "dim" if first_chunk_type == "reason" else "bright_white"
                _update_panel_content(
                    first_chunk_content, style=first_style, update_subtitle=True
                )
                # Parse title to get agent_name and model_name
                agent_name = ""
                model_name = ""
                if "·" in title:
                    parts = title.split("·")
                    if len(parts) > 1:
                        agent_name = parts[0].strip()
                        if "(" in parts[1]:
                            model_name = parts[1].split("(")[1].rstrip(")").strip()
                # Send stream start event
                emit_output(
                    OutputEvent(
                        text="",
                        output_type=OutputType.STREAM_START,
                        timestamp=_get_timestamp(),
                        context={
                            "agent_name": agent_name,
                            "model_name": model_name,
                            "start_time": start_time,
                        },
                    )
                )

                # Send the first chunk (to avoid losing the first chunk)
                if first_chunk_content:
                    emit_output(
                        OutputEvent(
                            text=first_chunk_content,
                            output_type=OutputType.STREAM_CHUNK,
                            timestamp=_get_timestamp(),
                        )
                    )

            buffer: List[Tuple[str, str]] = []
            last_update_time = time.time()
            update_interval = 0.2
            min_buffer_size = 5

            def _flush_buffer():
                nonlocal buffer, last_update_time
                if buffer:
                    for content, style in buffer:
                        _update_panel_content(content, style=style)
                    buffer = []
                    last_update_time = time.time()

            try:
                for chunk_type, chunk_content in chat_iterator:
                    if not chunk_content:
                        continue
                    # Show all content; reason uses gray style
                    style = "dim" if chunk_type == "reason" else "bright_white"
                    buffer.append((chunk_content, style))
                    # Only content type is appended to response
                    if chunk_type == "content":
                        response += chunk_content
                    # Collect reason type content
                    elif chunk_type == "reason":
                        reasoning_content += chunk_content
                    # Send streaming chunk event (both reason and content are sent)
                    if chunk_content:
                        emit_output(
                            OutputEvent(
                                text=chunk_content,
                                output_type=OutputType.STREAM_CHUNK,
                                timestamp=_get_timestamp(),
                            )
                        )

                    # Detect repeated output in real time (including reasoning content)
                    total_len = len(response) + len(reasoning_content)
                    if total_len - last_repeating_check_len >= repeating_check_interval:
                        last_repeating_check_len = total_len
                        combined_text = reasoning_content + response
                        is_repeating, _, _, _ = is_repeating_text(combined_text)
                        if is_repeating:
                            _flush_buffer()
                            PrettyOutput.auto_print(
                                "⚠ Model output detected as stuck in a repetition, will retry automatically"
                            )
                            return "", "", 0.0

                    if max_output > 0 and len(response) >= max_output:
                        _flush_buffer()
                        append_session_history(message, response)
                        break

                    current_time = time.time()
                    should_update = (
                        len(buffer) >= min_buffer_size
                        or (current_time - last_update_time) >= update_interval
                    )

                    if should_update:
                        _flush_buffer()

                    if is_immediate_abort() and check_interrupt():
                        _flush_buffer()
                        append_session_history(message, response)
                        break
            except Exception as e:
                # On exception, print the error message and return the collected content
                PrettyOutput.auto_print(f"⚠️ Streaming output exception: {e}")
                if raise_on_error:
                    raise
                _flush_buffer()
                append_session_history(message, response)
                return response, reasoning_content, first_token_time

            _flush_buffer()
            end_time = time.time()
            duration = end_time - start_time
            _update_panel_content("", update_subtitle=True, show_cursor=False)
            with _lock:
                _update_panel_subtitle(
                    panel,
                    response,
                    reasoning_content,
                    is_completed=True,
                    duration=duration,
                    first_tok_time=first_token_time,
                )
                live.update(panel)

        # Send stream end event
        response_tokens = (
            get_context_token_count(response)
            + get_context_token_count(reasoning_content)
            if get_context_token_count is not None
            else 0
        )
        generation_time = (
            duration - first_token_time if duration > first_token_time else duration
        )
        tokens_per_second = (
            response_tokens / generation_time if generation_time > 0 else 0
        )
        emit_output(
            OutputEvent(
                text="",
                output_type=OutputType.STREAM_END,
                timestamp=_get_timestamp(),
                context={
                    "duration": duration,
                    "first_token_time": first_token_time,
                    "tokens": response_tokens,
                    "tokens_per_second": tokens_per_second,
                },
            )
        )

        setattr(Heading, "__rich_console__", _original_rich_console)

        return response, reasoning_content, first_token_time

    @staticmethod
    def stream_chat_simple(
        chat_iterator: Generator[Tuple[str, str], None, None],
        prefix: str,
        start_time: float,
        message: str = "",
        max_output: int = 0,
        check_interrupt: Callable[[], bool] = lambda: False,
        append_session_history: Callable[[str, str], None] = lambda a, b: None,
        get_context_token_count: Optional[Callable[[str], int]] = None,
        get_used_token_count: Optional[Callable[[], int]] = None,
        get_platform_max_input_token_count: Optional[Callable[[], int]] = None,
        raise_on_error: bool = False,
    ) -> Tuple[str, str, float]:
        """
        Use simple mode for streaming chat output (print character by character).

        Parameters:
            chat_iterator: chat response iterator
            prefix: output prefix (e.g. "🤖 Model output - xxx")
            start_time: start timestamp
            message: user message (used to save history on interrupt)
            max_output: maximum output length, 0 means unlimited
            check_interrupt: callback to check whether an interrupt is requested
            append_session_history: callback to append session history
            get_context_token_count: callback to compute the token count of text (used to display speed, optional)
            output_sink: output backend (optional), used for streaming in Gateway mode
            raise_on_error: whether to re-raise exceptions during streaming (default False,
                keeping the existing behavior of "print the error and return the collected content")

        Returns:
            Tuple[str, str, float]: (model response, reasoning content, first token time)
        """
        import time

        from haijunbot.haijunbot_utils.utils import is_repeating_text

        # Parse prefix to get agent_name and model_name
        agent_name = ""
        model_name = ""
        if "·" in prefix:
            parts = prefix.split("·")
            if len(parts) > 1:
                agent_name = parts[0].replace("🤖 Model output - ", "").strip()
                if "(" in parts[1]:
                    model_name = parts[1].split("(")[1].rstrip(")").strip()

        console.print(prefix, soft_wrap=False)
        response = ""
        reasoning_content = ""
        first_token_time = 0.0
        last_repeating_check_len = 0
        repeating_check_interval = 100

        # Send stream start event
        emit_output(
            OutputEvent(
                text="",
                output_type=OutputType.STREAM_START,
                timestamp=_get_timestamp(),
                context={
                    "agent_name": agent_name,
                    "model_name": model_name,
                    "start_time": start_time,
                },
            )
        )

        try:
            for chunk_type, chunk_content in chat_iterator:
                if chunk_content and first_token_time == 0.0:
                    first_token_time = time.time() - start_time
                # When printing, both reason and content are shown; reason uses gray style
                style = "dim" if chunk_type == "reason" else "bright_white"
                console.print(chunk_content, end="", style=style)
                # When returning, only content type is appended
                if chunk_type == "content":
                    response += chunk_content
                # Collect reason type content
                elif chunk_type == "reason":
                    reasoning_content += chunk_content
                # Send streaming chunk event
                if chunk_content:
                    emit_output(
                        OutputEvent(
                            text=chunk_content,
                            output_type=OutputType.STREAM_CHUNK,
                            timestamp=_get_timestamp(),
                        )
                    )

                # Detect repeated output in real time (including reasoning content)
                total_len = len(response) + len(reasoning_content)
                if total_len - last_repeating_check_len >= repeating_check_interval:
                    last_repeating_check_len = total_len
                    combined_text = reasoning_content + response
                    is_repeating, _, _, _ = is_repeating_text(combined_text)
                    if is_repeating:
                        PrettyOutput.auto_print("⚠ Model output detected as stuck in a repetition, will retry automatically")
                        return "", "", 0.0

                if max_output > 0 and len(response) >= max_output:
                    append_session_history(message, response)
                    return response, reasoning_content, first_token_time
                if check_interrupt():
                    append_session_history(message, response)
                    return response, reasoning_content, first_token_time
        except Exception as e:
            # On exception, print the error message and return the collected content
            PrettyOutput.auto_print(f"⚠️ Streaming output exception: {e}")
            if raise_on_error:
                raise
            append_session_history(message, response)
            return response, reasoning_content, first_token_time

        console.print()
        end_time = time.time()
        duration = end_time - start_time
        response_tokens = (
            get_context_token_count(response)
            + get_context_token_count(reasoning_content)
            if get_context_token_count is not None
            else 0
        )

        generation_time = (
            duration - first_token_time if duration > first_token_time else duration
        )
        tokens_per_second = (
            response_tokens / generation_time if generation_time > 0 else 0
        )
        # Compute the currently used token count and the total token count
        used_tokens = 0
        max_tokens = 0
        try:
            if get_used_token_count is not None:
                used_tokens = get_used_token_count() + response_tokens
            if get_platform_max_input_token_count is not None:
                max_tokens = get_platform_max_input_token_count()
        except Exception:
            pass

        if max_tokens > 0:
            PrettyOutput.auto_print(
                f"✅ Conversation completed in: {duration:.2f}s | first token: {first_token_time:.2f}s | speed: {tokens_per_second:.1f} tokens/s | "
                f"Token: {used_tokens}/{max_tokens}"
            )
        else:
            PrettyOutput.auto_print(
                f"✅ Conversation completed in: {duration:.2f}s | first token: {first_token_time:.2f}s | speed: {tokens_per_second:.1f} tokens/s"
            )

        # Send stream end event
        emit_output(
            OutputEvent(
                text="",
                output_type=OutputType.STREAM_END,
                timestamp=_get_timestamp(),
                context={
                    "duration": duration,
                    "first_token_time": first_token_time,
                    "tokens": response_tokens,
                    "tokens_per_second": tokens_per_second,
                },
            )
        )

        return response, reasoning_content, first_token_time
