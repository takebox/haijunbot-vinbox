# -*- coding: utf-8 -*-
"""
PromptManager: uniformly manages the construction logic of the Agent's system prompt and addon prompt.

Design goals (phase one, minimal changes):
- Provide a standalone prompt-construction class without changing existing behavior
- Land the construction logic first, and gradually delegate to it in Agent later
- Keep compatibility with the existing tool/memory system
"""

from typing import TYPE_CHECKING
from typing import Any

from haijunbot.haijunbot_tools.registry import ToolRegistry
from haijunbot.haijunbot_utils.tag import ot

if TYPE_CHECKING:
    # Avoid runtime circular dependencies; for type annotation only
    from . import Agent


class PromptManager:
    """
    Prompt manager: responsible for constructing the system prompt and the default addon prompt.
    Note: this class does not directly access the model; it is only responsible for assembling strings.
    """

    def __init__(self, agent: "Agent"):
        self.agent = agent

    # ----------------------------
    # System prompt construction
    # ----------------------------
    def build_system_prompt(self, agent_: Any) -> str:
        """
        Construct the system prompt, reusing the existing tool-usage-prompt generation logic to keep behavior consistent.
        When native function calling is active, the text tool list/JSON help is no longer injected (tools are provided by the API tools).
        """
        if self.agent._native_active():
            # Native function calling: the tool list is provided by the API tools; the text tool list/JSON help is no longer injected,
            # but the guidance to "load rules/tracks on demand" is kept, so the model can also actively use auto_select_rule / load_rule mid-task.
            action_prompt = """
<rules>
# ❗ Important rules (strictly follow; violating them easily causes errors)
- **When tracks/rules are insufficient**: if the current tools are not up to the job or relevant knowledge is missing, use `auto_select_rule` to load the relevant rules and tracks—it automatically selects the most suitable rules based on the task (at most 5); you may also use `load_rule` to load a specified rule file by path.
</rules>
"""
        else:
            action_prompt = self.agent.get_tool_usage_prompt()

        # The rule index has been removed; the automatic rule-selection feature is now used

        # Check whether the task_list_manager tool is available
        task_list_manager_note = ""
        tool_registry = self.agent.get_tool_registry()
        if isinstance(tool_registry, ToolRegistry):
            task_list_tool = tool_registry.get_tool("task_list_manager")
            if task_list_tool:
                task_list_manager_note = """
<task_list_manager_guide>
# Task list management tool usage guide
**Key point: as the first step of handling a task, first decide whether a task list needs to be created**
Before starting a task, first assess its complexity. **Strongly recommended: any task that requires two or more steps should use `task_list_manager` to create a task list**. Even if the task looks simple, using a task list helps track progress, record results, and make adjustments.

**Types of tasks that should be planned in advance (meeting any one of these conditions counts):**
- **Multi-step tasks**: tasks that require two or more steps to complete (e.g. implementing a complete feature module, refactoring a large codebase, modifying multiple files)
- **Tasks with dependencies**: tasks that depend on each other and must be executed in order (e.g. first set up the database tables, then implement the API)
- **Tasks that can be parallelized**: independent tasks that can proceed simultaneously (e.g. developing multiple feature modules in parallel)
- **Long-term tasks that need progress tracking**: long-term projects completed in stages with progress tracking
- **Tasks requiring different Agent types**: some tasks need a code Agent, others a general Agent (e.g. code implementation + documentation writing)
- **Tasks requiring staged verification**: each stage must be verified before continuing to the next (e.g. implement the basic feature first, then add advanced features after tests pass)

**🚨 Scenarios where it is strongly recommended:**
1. **Step one: decide whether splitting is needed** - if the task matches the above types, immediately use `add_tasks` to create a task list
2. **Split the tasks at the same time** - provide `main_goal` and `tasks_info` together in `add_tasks`, creating the list and adding all subtasks in one go
3. **Mandatory additional_info** - provide a detailed additional_info parameter before each `execute_task`
4. **Execute the tasks** - use `execute_task` to execute tasks one by one; the system automatically creates a sub-Agent

**Core features:**
- Create a task list and add tasks: use the `add_tasks` operation; you may provide `tasks_info` to create the list and add all tasks in one go
- Manage task execution: automatically create sub-Agents to execute tasks via `execute_task`
- Track task status: view the task execution process and results

**Usage recommendations:**
- **Key principle**: as the first step of handling a task, decide whether splitting is needed; if so, immediately create a task list, to avoid discovering the need to split only after executing some steps
- **Do not split simple tasks**: if a task can be completed in 1-3 steps, involves modifying only a single file, or requires only a single tool call, never create a task list; let the main Agent execute it directly
- **Avoid over-splitting**: task splitting should keep a reasonable granularity; avoid splitting simple tasks into too many overly fine subtasks, which increases the information-transfer burden and may reduce efficiency
- **Splitting assessment points**: any task that can be completed in 1-2 steps should preferably be executed directly by the main Agent; do not create a sub-Agent
- It is recommended to provide `tasks_info` together in `add_tasks`, creating the list and adding all tasks in one go
- Dependencies between tasks can be referenced by task name (the system matches automatically)
- A task list helps better organize and manage the task execution process, ensuring tasks are executed in the correct order
</task_list_manager_guide>
"""

        system_tools_info = self._get_system_tools_info()

        return f"""
{self.agent.system_prompt}

{action_prompt}

{task_list_manager_note}

{system_tools_info}

"""

    # ----------------------------
    # System tool information
    # ----------------------------
    def _get_system_tools_info(self) -> str:
        """
        Return the system tool information.

        Returns:
            str: the formatted system tool information string, for the AI assistant to understand the available tools
        """
        import os
        import platform
        from datetime import datetime

        current_work_dir = os.getcwd()
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        os_type = platform.system()  # Linux, Darwin, Windows
        os_release = (
            platform.freedesktop_os_release().get("PRETTY_NAME", platform.release())
            if os_type == "Linux"
            else platform.version()
        )

        return f"""
<system_info>
- Current working directory: {current_work_dir}
- Current time: {current_time}
- System type: {os_type}
- System distribution: {os_release}
</system_info>"""

    def build_default_addon_prompt(self, need_complete: bool) -> str:
        """
        Construct the default addon prompt (kept consistent with the behavior of Agent.make_default_addon_prompt).
        Only performs string assembly; does not manipulate session state.
        """
        # Structured system instructions
        action_handlers = ", ".join(
            [handler.name() for handler in self.agent.output_handler]
        )

        # Task completion hint
        complete_prompt = (
            f"- If the whole task is already complete, output only {ot('!!!COMPLETE!!!')}, and output nothing else; the task summary will be asked in a subsequent interaction."
            if need_complete and self.agent.auto_complete
            else ""
        )

        # When native function calling is active, do not inject the text JSON/operation list instructions; the text protocol mode keeps them
        native = bool(self.agent._native_active())

        # Get the current model type and the mode hint
        mode_hint = ""
        try:
            from haijunbot.haijunbot_agent.builtin_input_handler import (
                get_platform_type_from_agent,
            )

            current_model_type = get_platform_type_from_agent(self.agent)
            model_type_display = {
                "smart": "Smart",
                "normal": "Normal",
                "cheap": "Cheap",
            }.get(current_model_type, current_model_type)

            # Infer the possible mode based on the model type
            mode_hint = f"\n    - Currently using the {model_type_display} model"
        except Exception:
            # If retrieval fails, do not add the mode hint
            pass

        if native:
            tool_lines = (
                "    - When an operation needs to be performed, directly issue a tool call; the tool name and parameters are based on the tool definitions given in the current context"
                "\n        - You may call one or more mutually independent tools at a time; when there is a dependency, wait for the previous result before calling the next one"
            )
            actions_line = mode_hint
        else:
            tool_registry = self.agent.get_tool_registry()
            memory_prompts = self.agent.memory_manager.add_memory_prompts_to_addon(
                "", tool_registry if isinstance(tool_registry, ToolRegistry) else None
            )
            tool_lines = (
                "    - Tool calls output a JSON object directly, without any tag wrapping"
                "\n        - You may call one or more tools at a time, but multiple tools must be **mutually independent**"
                "(the result/side effect of the former cannot be the input of the latter); when a dependency exists, call the depended-upon tool first, and call the next after the result arrives"
            )
            actions_line = f"- Available operations: {action_handlers}{memory_prompts}{mode_hint}"

        addon_prompt = f"""
<system_prompt>
    First judge whether the whole task is already complete:

    - If complete:
        {complete_prompt if complete_prompt else "- Explain the reason for completion and stop; do not issue new tool calls"}
    - If not complete, continue with the next step:
        - When writing large content such as files, do not write it all at once; write it in multiple passes to avoid being truncated by the length limit
        - When the requirement or information is unclear, first ask the user for clarification
        - If execution fails 5 times in a row, stop and ask the user how to proceed
        {tool_lines}
        {actions_line}

    Supplement: if the task of the current phase is already complete and the previous context is of little value, you may output {ot("!!!SUMMARY!!!")} to trigger compression and clear the history, so as to start a new phase.
</system_prompt>

Please continue.
"""
        return addon_prompt
