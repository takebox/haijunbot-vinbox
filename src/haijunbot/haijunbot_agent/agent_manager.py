# -*- coding: utf-8 -*-
"""Agent manager module, responsible for Agent initialization and task execution"""

from typing import Callable
from typing import List
from typing import Optional
from typing import Union

import typer

from haijunbot.haijunbot_agent import Agent
from haijunbot.haijunbot_agent import get_multiline_input
from haijunbot.haijunbot_agent import origin_agent_system_prompt
from haijunbot.haijunbot_agent.task_manager import TaskManager
from haijunbot.haijunbot_utils.config import is_non_interactive
from haijunbot.haijunbot_utils.config import is_skip_predefined_tasks
from haijunbot.haijunbot_utils.output import PrettyOutput


class AgentManager:
    """Agent manager, responsible for the Agent's lifecycle management"""

    def __init__(
        self,
        tool_group: Optional[str] = None,
        restore_session: Optional[Union[bool, str]] = None,
        use_methodology: Optional[bool] = None,
        use_analysis: Optional[bool] = None,
        multiline_inputer: Optional[Callable[[str], str]] = None,
        confirm_callback: Optional[Callable[[str, bool], bool]] = None,
        non_interactive: Optional[bool] = None,
        allow_savesession: bool = False,
        rule_names: Optional[str] = None,
        optimize_system_prompt: bool = False,
        quick_mode: bool = False,
    ):
        self.tool_group = tool_group
        self.restore_session = restore_session
        self.use_methodology = use_methodology
        self.use_analysis = use_analysis
        self.agent: Optional[Agent] = None
        # Optional: inject input and confirmation callbacks, used to replace interaction in frontends such as Web mode
        self.multiline_inputer = multiline_inputer
        self.confirm_callback = confirm_callback
        self.non_interactive = non_interactive
        self.allow_savesession = allow_savesession
        self.rule_names = rule_names
        self.optimize_system_prompt = optimize_system_prompt
        self.quick_mode = quick_mode

    def _merge_rule_names(self, eli_rule_names: Optional[str]) -> Optional[str]:
        """Merge the default rules from the config file and the command-line rules

        Args:
            eli_rule_names: Rule names passed from the command line (a comma-separated string)

        Returns:
            Optional[str]: The merged rule names (a comma-separated string), or None if both are empty
        """
        from haijunbot.haijunbot_utils.config import get_default_rule_names

        # Get the default rules from the config file
        default_rules = get_default_rule_names()

        # Parse the command-line rules
        eli_rules: List[str] = []
        if eli_rule_names and eli_rule_names.strip():
            eli_rules = [
                name.strip() for name in eli_rule_names.split(",") if name.strip()
            ]

        # If neither is present, return None
        if not default_rules and not eli_rules:
            return None

        # Merge and deduplicate
        all_rules = list(dict.fromkeys(default_rules + eli_rules))  # Order-preserving deduplication

        # Convert to a comma-separated string
        return ",".join(all_rules) if all_rules else None

    def initialize(self) -> Agent:
        """Initialize the Agent"""
        # If a tool_group parameter is provided, set it in the config
        if self.tool_group:
            from haijunbot.haijunbot_utils.config import set_config

            set_config("tool_group", self.tool_group)

        # Merge the default rules and the command-line rules
        merged_rule_names = self._merge_rule_names(self.rule_names)

        self.agent = Agent(
            system_prompt=origin_agent_system_prompt,
            need_summary=False,
            use_methodology=self.use_methodology,
            use_analysis=self.use_analysis,
            multiline_inputer=self.multiline_inputer,
            confirm_callback=self.confirm_callback,
            non_interactive=self.non_interactive,
            auto_complete=self.non_interactive or False,  # Auto-complete in non-interactive mode
            allow_savesession=self.allow_savesession,
            rule_names=merged_rule_names,
            optimize_system_prompt=self.optimize_system_prompt,
            quick_mode=self.quick_mode,
        )

        # Try to restore the session
        if self.restore_session:
            if self.agent.restore_session(self.restore_session):
                PrettyOutput.auto_print("✅ Session restored successfully.")
            else:
                PrettyOutput.auto_print("⚠️ Unable to restore session.")

        return self.agent

    def run_task(self, task_content: Optional[str] = None) -> None:
        """Run a task"""
        if not self.agent:
            raise RuntimeError("Agent not initialized")

        # Prioritize handling a task passed directly from the command line
        if task_content:
            self.agent.run(task_content)
            raise typer.Exit(code=0)

        # Handle predefined tasks (skip in non-interactive mode; support config to skip loading; skip when a task is specified on the command line)
        if (
            not is_non_interactive()
            and not is_skip_predefined_tasks()
            and not task_content
            and self.agent.first
        ):
            task_manager = TaskManager()
            tasks = task_manager.load_tasks()
            if tasks and (selected_task := task_manager.select_task(tasks)):
                PrettyOutput.auto_print(f"ℹ️ Starting task: \n{selected_task}")  # ty: ignore[possibly-unresolved-reference]
                self.agent.run(selected_task)  # ty: ignore[possibly-unresolved-reference]
                raise typer.Exit(code=0)

        # Get user input
        user_input = get_multiline_input("Please enter your task (Ctrl+C to exit)")
        if user_input:
            self.agent.run(user_input)
        raise typer.Exit(code=0)
