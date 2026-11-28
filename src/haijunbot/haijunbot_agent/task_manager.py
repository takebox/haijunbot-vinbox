# -*- coding: utf-8 -*-
"""Task management module, responsible for loading and selecting predefined tasks"""

import os
from typing import cast


import yaml  # type: ignore[import-untyped]
from prompt_toolkit import prompt

from haijunbot.haijunbot_agent import get_multiline_input
from haijunbot.haijunbot_agent import user_confirm
from haijunbot.haijunbot_agent.utils import join_prompts
from haijunbot.haijunbot_utils.config import get_data_dir
from haijunbot.haijunbot_utils.fzf import fzf_select
from haijunbot.haijunbot_utils.output import PrettyOutput


class TaskManager:
    """Task manager, responsible for loading and selecting predefined tasks"""

    @staticmethod
    def load_tasks() -> dict[str, str]:
        """Load tasks from .haijunbot files in user home and current directory."""
        tasks: dict[str, str] = {}

        # Check pre-command in data directory
        data_dir = get_data_dir()
        pre_command_path = os.path.join(data_dir, "pre-command")
        if os.path.exists(pre_command_path):
            PrettyOutput.auto_print(f"ℹ️ Loading predefined tasks from {pre_command_path}...")
            try:
                with open(
                    pre_command_path, "r", encoding="utf-8", errors="ignore"
                ) as f:
                    user_tasks = yaml.safe_load(f)
                if isinstance(user_tasks, dict):
                    for name, desc in user_tasks.items():
                        if desc:
                            tasks[str(name)] = str(desc)
                PrettyOutput.auto_print(f"✅ Predefined tasks loaded from {pre_command_path}")
            except (yaml.YAMLError, OSError):
                PrettyOutput.auto_print(f"❌ Failed to load predefined tasks from {pre_command_path}")

        # Check .haijunbot/pre-command in current directory
        pre_command_path = ".haijunbot/pre-command"
        if os.path.exists(pre_command_path):
            abs_path = os.path.abspath(pre_command_path)
            PrettyOutput.auto_print(f"ℹ️ Loading predefined tasks from {abs_path}...")
            try:
                with open(
                    pre_command_path, "r", encoding="utf-8", errors="ignore"
                ) as f:
                    local_tasks = yaml.safe_load(f)
                if isinstance(local_tasks, dict):
                    for name, desc in local_tasks.items():
                        if desc:
                            tasks[str(name)] = str(desc)
                PrettyOutput.auto_print(f"✅ Predefined tasks loaded from {pre_command_path}")
            except (yaml.YAMLError, OSError):
                PrettyOutput.auto_print(f"❌ Failed to load predefined tasks from {pre_command_path}")

        return tasks

    @staticmethod
    def select_task(tasks: dict[str, str]) -> str:
        """Let user select a task from the list or skip. Returns task description if selected."""
        if not tasks:
            return ""

        task_names = list(tasks.keys())
        # Display predefined tasks using a markdown table
        headers = ["No.", "Task Name"]
        rows = [[str(i), name] for i, name in enumerate(task_names, 1)]
        header_row = "| " + " | ".join(headers) + " |"
        separator_row = "| " + " | ".join(["---"] * len(headers)) + " |"
        data_rows = ["| " + " | ".join(row) + "|" for row in rows]
        md_content = (
            "## Predefined Tasks\n\n"
            + header_row
            + "\n"
            + separator_row
            + "\n"
            + "\n".join(data_rows)
        )
        PrettyOutput.print_markdown(md_content)
        PrettyOutput.auto_print("ℹ️ Please select a task to execute (enter a number or use the up/down keys):")

        # Try fzf selection first (with numbered options and a skip option)
        fzf_list = [f"{0:>3} | Skip predefined tasks"] + [
            f"{i:>3} | {name}" for i, name in enumerate(task_names, 1)
        ]
        selected_str = fzf_select(fzf_list, prompt="Select a task number (ESC to skip) > ")
        if selected_str:
            try:
                num_part = selected_str.split("|", 1)[0].strip()
                idx = int(num_part)
                if idx == 0:
                    return ""
                if 1 <= idx <= len(task_names):
                    selected_task = tasks[task_names[idx - 1]]
                    PrettyOutput.auto_print(f"ℹ️ About to execute task:\n {selected_task}")
                    # Ask whether supplementary information is needed
                    need_additional = user_confirm(
                        "Do you want to add supplementary information for this task?", default=False
                    )
                    if need_additional:
                        additional_input = get_multiline_input("Please enter supplementary information")
                        if additional_input:
                            selected_task = cast(
                                str,
                                join_prompts(
                                    [selected_task, f"Supplementary information:\n{additional_input}"]
                                ),
                            )
                    return selected_task
            except Exception:
                # If parsing fails, fall back to manual input
                pass

        while True:
            try:
                choice_str = prompt(
                    "\nPlease select a task number (0 or press Enter directly to skip predefined tasks): "
                ).strip()
                if not choice_str:
                    return ""

                choice = int(choice_str)
                if choice == 0:
                    return ""
                if 1 <= choice <= len(task_names):
                    selected_task = tasks[task_names[choice - 1]]
                    PrettyOutput.auto_print(f"ℹ️ About to execute task:\n {selected_task}")
                    # Ask whether supplementary information is needed
                    need_additional = user_confirm(
                        "Do you want to add supplementary information for this task?", default=False
                    )
                    if need_additional:
                        additional_input = get_multiline_input("Please enter supplementary information")
                        if additional_input:
                            selected_task = cast(
                                str,
                                join_prompts(
                                    [selected_task, f"Supplementary information:\n{additional_input}"]
                                ),
                            )
                    return selected_task
                PrettyOutput.auto_print("⚠️ Invalid choice. Please select a number from the list.")

            except (KeyboardInterrupt, EOFError):
                return ""
            except ValueError as val_err:
                PrettyOutput.auto_print(f"❌ Failed to select task: {str(val_err)}")
