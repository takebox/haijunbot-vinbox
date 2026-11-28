# -*- coding: utf-8 -*-
"""
sub_code_agent tool
Hands a subtask to CodeAgent for execution and returns the result.

Conventions:
- Required parameter: task
- Optional parameter: background
- Does not depend on the parent Agent; all configuration uses system defaults and global variables
- The sub Agent must auto-complete (auto_complete=True) and needs a summary (need_summary=True)
"""

from typing import Any, Dict, List

from haijunbot.haijunbot_code_agent.code_agent import CodeAgent
from haijunbot.haijunbot_utils.exception_utils import save_exception

_MAX_CHILD_MESSAGES = 60
_MAX_CHILD_MSG_CHARS = 8000


def _trim_child_context(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Trim the parent context inherited by the sub Agent, to avoid large tool outputs/long history being billed repeatedly by each subagent.

    Keep only the most recent several messages, and truncate overly long single-text content.
    """
    out: List[Dict[str, Any]] = []
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


class SubCodeAgentTool:
    """
    Use CodeAgent to host the execution of a subtask, and clean up the CodeAgent instance immediately after execution.
    - Not registered globally
    - Uses the system default/global configuration
    - Enables auto-completion and summarization
    """

    # Must match the file name, for ToolRegistry to auto-register
    name = "sub_code_agent"
    description = "Hand a relatively independent coding subtask to a new CodeAgent to execute in an isolated session and return a summary, avoiding pollution of the main context; nesting within a subagent is forbidden."
    parameters = {
        "type": "object",
        "properties": {
            "task": {
                "type": "string",
                "description": "The subtask content to execute (required)",
            },
            "background": {
                "type": "string",
                "description": "Task background and known information (optional; will be provided to the sub Agent together with the task)",
            },
            "name": {
                "type": "string",
                "description": "Sub Agent name (optional; used to identify and distinguish different sub Agents)",
            },
            "goal": {
                "type": "string",
                "description": "Goal description of the subtask (optional; used to clarify the sub Agent's execution goal)",
            },
        },
        "required": ["task"],
    }

    def execute(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the coding subtask and return the result (hosted by CodeAgent).
        Returns:
          - success: whether it succeeded
          - stdout: the CodeAgent execution result (a string; if None, returns "Task execution completed")
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

            # Read the sub Agent name (optional)
            agent_name: str = str(args.get("name", "")).strip()

            # Inherit the parent Agent's model group and tool usage set (to override defaults)
            parent_agent = args.get("agent")

            # Permission check: only CodeAgent may call this tool
            if parent_agent is not None:
                if not isinstance(parent_agent, CodeAgent):
                    return {
                        "success": False,
                        "stdout": "",
                        "stderr": "The sub_code_agent tool only supports calls from CodeAgent; the current Agent type does not support this tool.",
                    }

            # Get the parent Agent's conversation history (before creating the CodeAgent)
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
            # If the parent Agent was not injected, try to get the current or any registered Agent from the globals
            if parent_agent is None:
                try:
                    from haijunbot.haijunbot_utils import globals as G  # Lazy import to avoid circular imports

                    curr = G.get_current_agent_name()
                    if curr:
                        parent_agent = getattr(G, "global_agents", {}).get(curr)
                    if parent_agent is None and getattr(G, "global_agents", {}):
                        try:
                            parent_agent = next(iter(G.global_agents.values()))
                        except Exception:
                            parent_agent = None
                except Exception:
                    parent_agent = None

            use_tools: List[str] = []
            try:
                if parent_agent is not None:
                    parent_registry = parent_agent.get_tool_registry()
                    if parent_registry:
                        for t in parent_registry.get_all_tools():
                            if isinstance(t, dict) and t.get("name"):
                                use_tools.append(str(t["name"]))
            except Exception as e:
                save_exception(
                    e, module="haijunbot_tools.sub_code_agent", function="execute"
                )
                pass

            # Create CodeAgent: prefer the parent Agent's configuration for parameters (if obtainable), otherwise use defaults
            # Infer/inherit tool_group
            tool_group = None
            try:
                if parent_agent is not None:
                    tool_group = getattr(parent_agent, "tool_group", tool_group)
            except Exception as e:
                save_exception(
                    e, module="haijunbot_tools.sub_code_agent", function="execute"
                )
                pass

            # Based on the parent Agent's enabled tool set, derive append_tools (as an increment on top of CodeAgent's base tools)
            # Disable sub_agent and sub_code_agent to avoid infinite recursion
            forbidden_tools = {"sub_agent", "sub_code_agent"}
            append_tools = None
            try:
                base_tools = [
                    "execute_script",
                    "read_code",
                    "edit_file",
                    "edit_file_by_line",
                    "write_file",
                ]
                if use_tools:
                    # Filter out base tools and forbidden tools
                    extras = [
                        t
                        for t in use_tools
                        if t not in base_tools and t not in forbidden_tools
                    ]
                    append_tools = ",".join(extras) if extras else None
            except Exception:
                append_tools = None

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

            # Inherit the parent Agent's non-interactive mode setting
            # When the parent Agent has auto_complete=True or non_interactive=True, force the sub Agent into non-interactive mode
            parent_non_interactive = None
            parent_auto_complete = None
            try:
                if parent_agent is not None:
                    parent_non_interactive = getattr(
                        parent_agent, "non_interactive", None
                    )
                    parent_auto_complete = getattr(parent_agent, "auto_complete", None)
            except Exception:
                parent_non_interactive = None
                parent_auto_complete = None

            # Inherit the parent Agent's interaction configuration: when the parent Agent is non-interactive or auto-completes, force the sub Agent to be non-interactive;
            # otherwise the sub Agent stays interactive, consistent with the parent Agent.
            force_non_interactive = (
                parent_non_interactive is True or parent_auto_complete is True
            )

            # Automatically disable the review feature
            disable_review = True

            # Create CodeAgent, catching SystemExit exceptions (e.g., incomplete git configuration)
            try:
                code_agent = CodeAgent(
                    name=agent_name,
                    need_summary=True,
                    append_tools=append_tools,
                    tool_group=tool_group,
                    non_interactive=force_non_interactive,
                    rule_names=rule_names,
                    disable_review=disable_review,
                    auto_complete=True,
                )
                # Mark the current agent as a sub_agent, forbidding it from creating sub-type tasks or nesting sub_agents
                code_agent.set_user_data("__is_sub_agent__", True)
            except SystemExit as se:
                # Convert the underlying sys.exit into a tool error to avoid terminating the process
                return {
                    "success": False,
                    "stdout": "",
                    "stderr": f"Failed to initialize CodeAgent (git may not be configured or the current directory is not a git repository): {se}",
                }

            # The sub Agent needs to auto-complete
            try:
                # Sync the parent Agent tool usage set (if available), but disable sub_agent and sub_code_agent to avoid infinite recursion
                if use_tools:
                    forbidden_tools = {"sub_agent", "sub_code_agent"}
                    filtered_tools = [t for t in use_tools if t not in forbidden_tools]
                    if filtered_tools:
                        code_agent.set_use_tools(filtered_tools)
                # No longer fetch the model name from the parent Agent; use the system default configuration (in line with the "does not depend on the parent Agent" convention)
            except Exception as e:
                save_exception(
                    e, module="haijunbot_tools.sub_code_agent", function="execute"
                )
                pass

            # Set the inherited conversation history on the CodeAgent (after the CodeAgent is created)
            if parent_messages and hasattr(code_agent, "model"):
                try:
                    # Insert a role-switch note before the first user message
                    role_switch_note = """[Role switch note]
You are now a sub Agent (sub_code_agent), integrated with the parent Agent's complete conversation history and context.
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
                    code_agent.model.set_messages(modified_messages)
                    # The parent Agent history has been inherited; skip first-run initialization (rule selection, etc.)
                    code_agent.first = False
                except Exception:
                    # A failure to set does not affect the main flow
                    pass

            # Execute the subtask (no commit message prefix/suffix)
            ret = code_agent.run(enhanced_task)

            # Merge the sub agent's memory tags into the parent agent
            if parent_agent and hasattr(parent_agent, "add_memory_tags"):
                try:
                    child_tags = code_agent.get_memory_tags()
                    if child_tags:
                        parent_agent.add_memory_tags(child_tags)
                except Exception:
                    # A failure to merge tags does not affect the main functionality
                    pass

            return {
                "success": True,
                "stdout": ret,
                "stderr": "",
            }
        except Exception as e:
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Failed to execute subtask: {str(e)}",
            }
