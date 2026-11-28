# -*- coding: utf-8 -*-
import json
from typing import TYPE_CHECKING
from typing import Any
from typing import Dict
from typing import List
from typing import Tuple
from typing import Union

from haijunbot.haijunbot_utils.input import user_confirm
from haijunbot.haijunbot_utils.output import PrettyOutput

if TYPE_CHECKING:
    from haijunbot.haijunbot_agent import Agent


TERMINAL_SCREEN_COLUMNS = 300
TERMINAL_SCREEN_LINES = 100000


def _normalize_terminal_output(output_text: str) -> str:
    """Normalize the terminal output to the text ultimately visible to the user."""
    if not output_text:
        return output_text

    try:
        import pyte

        screen = pyte.Screen(TERMINAL_SCREEN_COLUMNS, TERMINAL_SCREEN_LINES)
        stream = pyte.Stream(screen)
        stream.feed(output_text)

        visible_lines: List[str] = []
        for row_index in range(screen.lines):
            row = screen.buffer[row_index]
            rendered_line = "".join(char.data for char in row.values()).rstrip()
            if rendered_line:
                visible_lines.append(rendered_line)

        normalized_output = "\n".join(visible_lines).strip()
        return normalized_output or output_text.strip()
    except Exception:
        return output_text.strip()


def _normalize_tool_result(tool_result: Any) -> Any:
    """Clean up terminal control output in the tool result, prioritizing keeping the existing return protocol unchanged."""
    if not isinstance(tool_result, tuple) or len(tool_result) != 2:
        return tool_result

    should_return, payload = tool_result
    if isinstance(payload, str):
        return should_return, _normalize_terminal_output(payload)

    return tool_result


def execute_tool_call(response: str, agent: "Agent") -> Tuple[bool, Any]:
    """
    Parses the model's response, identifies the appropriate tool, and executes it.

    Args:
        response: The response string from the model, potentially containing a tool call.
        agent: The agent instance, providing context like output handlers and settings.

    Returns:
        A tuple containing:
        - A boolean indicating if the tool's result should be returned to the user.
        - The result of the tool execution or an error message.
    """
    tool_list = []
    for handler in agent.output_handler:
        if handler.can_handle(response):
            tool_list.append(handler)

    # If multiple handlers of different types are detected (e.g. TOOL_CALL and other types), still report an error
    # But if there is only one handler (usually ToolRegistry), allow it to handle multiple tool calls
    if len(tool_list) > 1:
        error_message = (
            f"Operation failed: multiple operations of different types detected. Only one type of operation can be executed at a time."
            f"Attempted operations: {', '.join([handler.name() for handler in tool_list])}"
        )
        PrettyOutput.auto_print(f"⚠️ {error_message}")
        return False, error_message

    if not tool_list:
        return False, ""

    tool_to_execute = tool_list[0]

    # If confirmation is needed, print the tool details first
    if agent.execute_tool_confirm:
        # Parse the tool call information (may contain multiple tool calls)
        tool_infos = _parse_tool_call_info(response, tool_to_execute.name())
        if isinstance(tool_infos, list):
            # Multiple tool calls
            PrettyOutput.auto_print(f"🔧 Preparing to execute {len(tool_infos)} tool calls:")
            for idx, tool_info in enumerate(tool_infos, 1):
                PrettyOutput.auto_print(
                    f"  [{idx}] {tool_info.get('name', 'Unknown tool')}"
                )
                if tool_info.get("param_summary"):
                    PrettyOutput.auto_print(f"      Parameters: {tool_info['param_summary']}")
        elif tool_infos:
            # Single tool call
            PrettyOutput.auto_print(f"🔧 Preparing to execute tool: {tool_infos['name']}")
            if tool_infos.get("param_summary"):
                PrettyOutput.auto_print(f"   Parameters: {tool_infos['param_summary']}")
        else:
            # On parse failure, at least show the tool name
            PrettyOutput.auto_print(f"🔧 Preparing to execute tool: {tool_to_execute.name()}")

    if not agent.execute_tool_confirm or user_confirm(
        f"Execute {tool_to_execute.name()}? Confirm execution?", True
    ):
        try:
            result = tool_to_execute.handle(response, agent)
            return _normalize_tool_result(result)  # type: ignore[no-any-return]
        except Exception as e:
            PrettyOutput.auto_print(f"❌ Tool execution failed: {str(e)}")
            return False, str(e)

    return False, ""


def _parse_tool_call_info(
    response: str, handler_name: str
) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
    """Parse the tool call information from the response

    Args:
        response: the response string containing tool calls
        handler_name: the handler name (used as a fallback)

    Returns:
        Dict or List[Dict]: a dict for a single tool call, a list for multiple tool calls
    """
    try:
        # Use pure JSON scanning to extract tool calls
        from haijunbot.haijunbot_utils.utils import extract_json_from_text
        from haijunbot.haijunbot_utils.jsonnet_compat import loads as json_loads

        # Parse all tool calls: scan each JSON object's starting position in the text and extract them one by one
        tool_infos = []
        for i, ch in enumerate(response):
            if ch not in ("{", "["):
                continue
            json_str, _ = extract_json_from_text(response, i)
            if not json_str:
                continue
            try:
                tool_call = json_loads(json_str)
            except Exception:
                tool_call = json.loads(json_str)
            if not isinstance(tool_call, dict):
                continue
            name = tool_call.get("name", handler_name)
            args = tool_call.get("arguments", {})
            # Generate the parameter summary
            param_summary = _generate_param_summary(args)
            tool_infos.append({"name": name, "param_summary": param_summary})

        if len(tool_infos) == 0:
            return {"name": handler_name}
        elif len(tool_infos) == 1:
            return tool_infos[0]
        else:
            return tool_infos
    except Exception:
        # On parse failure, return the handler name
        return {"name": handler_name}


def _generate_param_summary(args: Dict[str, Any]) -> str:
    """Generate a parameter summary, filtering sensitive information

    Args:
        args: the tool parameter dict

    Returns:
        str: the parameter summary string
    """
    if not isinstance(args, dict) or not args:
        return ""

    # List of sensitive fields
    sensitive_keys = {"password", "token", "key", "secret", "auth", "credential"}

    summary_parts = []
    for key, value in args.items():
        if key.lower() in sensitive_keys:
            summary_parts.append(f"{key}='***'")
        elif isinstance(value, (dict, list)):
            summary_parts.append(f"{key}={type(value).__name__}({len(value)} items)")
        elif isinstance(value, str) and len(value) > 50:
            summary_parts.append(f"{key}='{value[:47]}...'")
        else:
            summary_parts.append(f"{key}={repr(value)}")

    if summary_parts:
        # Replace newlines in the parameter values with spaces to avoid newlines in the summary
        cleaned_parts = [
            part.replace("\n", " ").replace("\r", " ") for part in summary_parts
        ]
        return " | ".join(cleaned_parts)

    return ""
