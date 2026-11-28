"""
sub_agent tool
Hands a subtask to a general-purpose Agent for execution and returns the result.

Conventions:
- Required parameters: task, name
- Optional parameter: background
- Optional parameter: summary_prompt
- The sub Agent inherits the parent Agent's conversation history; no system_prompt needs to be specified
- Tool set: uses the system tool set by default (no need to pass use_tools)
- Inherits some parent Agent configuration: model_group, input_handler, execute_tool_confirm, multiline_inputer, non_interactive, use_methodology, use_analysis; other parameters must be provided explicitly
- The sub Agent must auto-complete (auto_complete=True) and needs a summary (need_summary=True)
"""

import json
from typing import Any, Dict

# -*- coding: utf-8 -*-

from haijunbot.haijunbot_agent import Agent
from haijunbot.haijunbot_utils.config import get_llm_group

_MAX_CHILD_MESSAGES = 60
_MAX_CHILD_MSG_CHARS = 8000


def _trim_child_context(messages):
    """Trim the parent context inherited by the sub Agent, to avoid large tool outputs/long history being billed repeatedly by each subagent."""
    out = []
    for msg in messages[-_MAX_CHILD_MESSAGES:]:
        if not isinstance(msg, dict):
            out.append(msg)
            continue
        m = dict(msg)
        content = m.get("content")
        if isinstance(content, str) and len(content) > _MAX_CHILD_MSG_CHARS:
            m["content"] = content[:_MAX_CHILD_MSG_CHARS] + "\n...(context too long, truncated)"
        out.append(m)
    return out


class SubAgentTool:
    """
    Temporarily creates a general-purpose Agent to execute a subtask, and cleans up immediately after execution.
    - Not registered globally
    - Uses the system default/global configuration
    - Enables auto-completion and summarization
    """

    # Must match the file name, for ToolRegistry to auto-register
    name = "sub_agent"
    description = "Hand an independent subtask to a new general-purpose Agent to execute in an isolated session and return a summary, avoiding pollution of the main context; nesting within a subagent is forbidden."
    parameters = {
        "type": "object",
        "properties": {
            "task": {
                "type": "string",
                "description": "The subtask content to execute (required)",
            },
            "name": {
                "type": "string",
                "description": "Sub Agent name (optional; used to identify and distinguish different sub Agents)",
            },
            "background": {
                "type": "string",
                "description": "Task background and known information (optional; will be provided to the sub Agent together with the task)",
            },
            "goal": {
                "type": "string",
                "description": "Goal description of the subtask (optional; used to clarify the sub Agent's execution goal)",
            },
        },
        "required": [
            "task",
        ],
    }

    def execute(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the subtask and return the result.
        Returns:
          - success: whether it succeeded
          - stdout: the result returned by the sub Agent (a string or a JSON string)
          - stderr: error message (if any)
        """
        try:
            task: str = str(args.get("task", "")).strip()
            if not task:
                return {
                    "success": False,
                    "stdout": "",
                    "stderr": "task cannot be empty",
                }

            # Read the background information and compose the task
            background: str = str(args.get("background", "")).strip()
            goal: str = str(args.get("goal", "")).strip()

            # Compose the task content
            task_parts = []
            if background:
                task_parts.append(f"Background information:\n{background}")
            task_parts.append(f"Task:\n{task}")
            if goal:
                task_parts.append(f"Goal:\n{goal}")
            enhanced_task = "\n\n".join(task_parts)

            # Does not inherit from the parent Agent; all key parameters must be provided explicitly by the caller
            need_summary = True

            # Read the sub Agent name
            agent_name = str(args.get("name", "")).strip()

            # If no name is provided, use the default name
            if not agent_name:
                agent_name = "SubAgent"

            # Create the sub Agent after inheriting some configuration from the parent Agent (if any)
            parent_agent = args.get("agent", None)
            # Get the parent Agent's conversation history (before creating the sub Agent)
            parent_messages = None
            if parent_agent and hasattr(parent_agent, "model"):
                try:
                    all_messages = parent_agent.model.get_messages()
                    # Filter out system messages and keep only the conversation history (user/assistant/tool messages)
                    parent_messages = [
                        msg for msg in all_messages if msg.get("role") != "system"
                    ]
                    if parent_messages:
                        parent_messages = _trim_child_context(parent_messages)
                except Exception:
                    # A failure to fetch does not affect the main flow
                    pass
            # Use the current model group (no longer inherited from parent_agent)
            get_llm_group()

            # Get the tool list from the parent Agent (for inheritance)
            use_tools: list = []
            try:
                if parent_agent is not None:
                    parent_registry = parent_agent.get_tool_registry()
                    if parent_registry:
                        for t in parent_registry.get_all_tools():
                            if isinstance(t, dict) and t.get("name"):
                                use_tools.append(str(t["name"]))
            except Exception:
                pass

            # Get the parent agent's rule name list for inheritance
            rule_names = None
            try:
                if parent_agent is not None and hasattr(
                    parent_agent, "loaded_rule_names"
                ):
                    parent_rules = getattr(parent_agent, "loaded_rule_names", [])
                    if parent_rules:
                        rule_names = ",".join(parent_rules)
            except Exception:
                rule_names = None

            parent_execute_tool_confirm = None
            parent_multiline_inputer = None
            parent_use_methodology = None
            parent_use_analysis = None
            parent_non_interactive = None  # Inherit the parent Agent's non-interactive mode setting
            parent_auto_complete = None  # Inherit the parent Agent's auto-complete setting
            try:
                if parent_agent is not None:
                    parent_execute_tool_confirm = getattr(
                        parent_agent, "execute_tool_confirm", None
                    )
                    parent_multiline_inputer = getattr(
                        parent_agent, "multiline_inputer", None
                    )
                    parent_use_methodology = getattr(
                        parent_agent, "use_methodology", None
                    )
                    parent_use_analysis = getattr(parent_agent, "use_analysis", None)
                    parent_non_interactive = getattr(
                        parent_agent, "non_interactive", None
                    )
                    parent_auto_complete = getattr(parent_agent, "auto_complete", None)
            except Exception:
                # Safe fallback: if configuration cannot be obtained from the parent Agent, keep it as None and use the system default
                pass

            # Inherit the parent Agent's interaction configuration: when the parent Agent is non-interactive or auto-completes, force the sub Agent to be non-interactive;
            # otherwise the sub Agent stays interactive, consistent with the parent Agent.
            force_non_interactive = (
                parent_non_interactive is True or parent_auto_complete is True
            )

            # Filter out forbidden tools to avoid infinite recursion
            forbidden_tools = {"sub_agent", "sub_code_agent"}
            filtered_use_tools = (
                [t for t in use_tools if t not in forbidden_tools]
                if use_tools
                else None
            )

            agent = Agent(
                name=agent_name,
                description="Temporary sub agent for executing a subtask",
                auto_complete=parent_auto_complete
                if parent_auto_complete is not None
                else True,
                use_tools=filtered_use_tools,
                execute_tool_confirm=parent_execute_tool_confirm,
                need_summary=need_summary,
                multiline_inputer=parent_multiline_inputer,
                use_methodology=parent_use_methodology,
                use_analysis=parent_use_analysis,
                force_save_memory=None,
                files=None,
                non_interactive=force_non_interactive,
                rule_names=rule_names,
            )
            # Mark the current agent as a sub_agent, forbidding it from creating sub-type tasks or nesting sub_agents
            agent.set_user_data("__is_sub_agent__", True)

            # Set the inherited conversation history on the sub Agent (after the Agent is created)
            if parent_messages and hasattr(agent, "model"):
                try:
                    # Insert a role-switch note before the first user message
                    role_switch_note = """[Role switch note]
You are now a sub Agent (sub_agent), integrated with the parent Agent's complete conversation history and context.
You understand the previous analysis process and the problems discovered, and can execute tasks directly based on this context.

Important notes:
- You are already a sub Agent; creating sub-type tasks or nesting sub Agents is forbidden
- The task list has been cleared; you do not inherit the parent Agent's task list
- Focus on completing the following subtask; no need to repeat already-completed steps
"""
                    # Find the first user message and insert the role-switch note before its content
                    modified_messages = []
                    first_user_inserted = False
                    for msg in parent_messages:
                        if msg.get("role") == "user" and not first_user_inserted:
                            # First user message; insert the note before the content
                            new_msg = msg.copy()
                            new_msg["content"] = (
                                role_switch_note + "\n" + msg.get("content", "")
                            )
                            modified_messages.append(new_msg)
                            first_user_inserted = True
                        else:
                            modified_messages.append(msg)
                    agent.model.set_messages(modified_messages)
                    # The parent Agent history has been inherited; skip first-run initialization (rule selection, etc.)
                    agent.first = False
                except Exception:
                    # A failure to set does not affect the main flow
                    pass

            # Disable sub_agent and sub_code_agent to avoid infinite recursion
            try:
                # Get the currently enabled tool list
                tool_registry = agent.get_tool_registry()
                if tool_registry:
                    current_tools = [
                        str(t.get("name"))
                        for t in tool_registry.get_all_tools()
                        if isinstance(t, dict) and t.get("name")
                    ]
                    # Filter out forbidden tools
                    forbidden_tools = {"sub_agent", "sub_code_agent"}
                    filtered_tools = [
                        t for t in current_tools if t not in forbidden_tools
                    ]
                    if filtered_tools:
                        agent.set_use_tools(filtered_tools)
            except Exception:
                # If disabling tools fails, it does not affect the main flow
                pass

            # Execute the task
            result = agent.run(enhanced_task)

            # Merge the sub agent's memory tags into the parent agent
            if parent_agent and hasattr(parent_agent, "add_memory_tags"):
                try:
                    child_tags = agent.get_memory_tags()
                    if child_tags:
                        parent_agent.add_memory_tags(child_tags)
                except Exception:
                    # A failure to merge tags does not affect the main functionality
                    pass

            # Normalize the output
            if isinstance(result, (dict, list)):
                stdout = json.dumps(result, ensure_ascii=False, indent=2)
            else:
                stdout = str(result) if result is not None else "Task execution completed"

            return {
                "success": True,
                "stdout": stdout,
                "stderr": "",
            }

        except Exception as e:
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Failed to execute subtask: {str(e)}",
            }
