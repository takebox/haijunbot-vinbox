# -*- coding: utf-8 -*-
from typing import List
from typing import Optional

from haijunbot.haijunbot_agent.protocols import OutputHandlerProtocol
from haijunbot.haijunbot_tools.registry import ToolRegistry


def get_tool_registry(
    output_handlers: List[OutputHandlerProtocol],
) -> Optional[ToolRegistry]:
    """Get the ToolRegistry instance from output handlers."""
    for handler in output_handlers:
        if isinstance(handler, ToolRegistry):
            return handler
    return None


def build_action_prompt(
    output_handlers: List[OutputHandlerProtocol],
    task_context: Optional[str] = None,
) -> str:
    """
    Builds the action prompt string from a list of output handlers.

    Args:
        output_handlers: A list of output handler instances.
        task_context: Optional task context text, passed to ToolRegistry.prompt()
            for tool pre-selection when the tool count is large.

    Returns:
        A formatted string containing the action prompt.
    """
    action_prompt = """
<actions>
# 🧰 Available Actions
The following are the actions available to you:
"""

    # Add tool list overview
    action_prompt += "\n<overview>\n## Action List\n"
    action_prompt += (
        "[" + ", ".join([handler.name() for handler in output_handlers]) + "]"
    )
    action_prompt += "\n</overview>"

    # Add details for each tool
    action_prompt += "\n\n<details>\n# 📝 Action Details\n"
    for handler in output_handlers:
        action_prompt += f"\n<tool>\n## {handler.name()}\n"
        # Get the handler's prompt and ensure correct formatting
        if isinstance(handler, ToolRegistry):
            handler_prompt = handler.prompt(task_context).strip()
        else:
            handler_prompt = handler.prompt().strip()
        # Adjust indentation to maintain hierarchy
        handler_prompt = "\n".join(
            "   " + line if line.strip() else line
            for line in handler_prompt.split("\n")
        )
        action_prompt += handler_prompt + "\n</tool>\n"

    # Add tool usage summary
    action_prompt += """
</details>

<rules>
# ❗ Important Rules (follow strictly; violations easily lead to errors)
1. **Tool calling**:
   - You may call one or more tools at a time
   - **Multi-tool constraint**: if you call multiple tools at once, they must be **mutually independent**
     * The result of tool A cannot be used as input for tool B
     * Tool B cannot depend on the side effects of tool A (such as creating files, changing state, etc.)
     * If there is a dependency between tools, you must call them in multiple rounds: first execute the depended-upon tool, wait for its result, then call the subsequent ones
2. **No fabricated results**: all conclusions must be based on the actual results returned by tools; do not speculate, assume, or make things up; wait until the tool finishes and you have the real result before proceeding to the next step.
3. **Wait for results before continuing**: before continuing, look at the current tool's return value; do not guess its result out of thin air.
4. **Digest results first**: fully process the current tool's return (including error messages and output text) before deciding the next step.
5. **Follow each tool's format**: call tools according to the format each tool requires, including parameter types, required fields, etc.
6. If you are unclear about how to use a given action, ask first.
7. **When tracks/rules are insufficient**: if the current tools are not up to the task or lack relevant knowledge, use `auto_select_rule` to load relevant rules and tracks—it will automatically pick the most suitable rules based on the task (up to 5).
"""

    action_prompt += "</rules>\n</actions>\n"
    return action_prompt
