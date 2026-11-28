# -*- coding: utf-8 -*-
"""HaijunBot Agent Dispatcher ELI

A convenience command for quickly launching hjb task dispatch.
"""

import os
import subprocess
import sys
from typing import Any, Optional

import typer
from typer.models import ArgumentInfo

from haijunbot.haijunbot_utils.output import PrettyOutput
from haijunbot.haijunbot_utils.input import (
    get_multiline_input as get_multiline_input_enhanced,
)
from haijunbot.haijunbot_utils.utils import init_env

# Create the typer app
app = typer.Typer(help="HaijunBot Agent Dispatcher - a convenience wrapper for hjb")


def _write_task_to_temp_file(task_content: str) -> str:
    """Write the task content to a temporary file and return the file path

    Args:
        task_content: Task content (a string)

    Returns:
        str: Temporary file path
    """
    # Use tempfile.mkstemp to create a temporary file in the /tmp directory
    import tempfile

    fd, temp_path = tempfile.mkstemp(
        suffix=".txt",
        prefix="hjbd_task_",
        text=True,
        dir="/tmp",
    )

    # Write the content
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(task_content)
        f.flush()
        os.fsync(f.fileno())

    PrettyOutput.auto_print(f"📝 Temporary file created: {temp_path}")
    return temp_path


def run_hjbd_dispatch(
    task: Any,
    is_dispatch_mode: bool = False,
    stay_in_session_after_exit: bool = True,
    force_dispatch: bool = False,
) -> None:
    """Execute hjb -n -d --task <task>"""
    # Ensure task is string content rather than a type object
    if isinstance(task, str):
        task_str = task
    elif isinstance(task, ArgumentInfo):
        # Handle typer's ArgumentInfo object and extract the default attribute
        task_str = task.default if task.default is not None else ""
    else:
        # Handle non-string types and try to get the actual value
        task_str = str(task) if task is not None else ""

    # Check whether task_str is empty
    if not task_str or not task_str.strip():
        PrettyOutput.auto_print(
            f"❌ Error: task content is empty and cannot be executed. task type: {type(task).__name__}, task value: {task}"
        )
        sys.exit(1)

    # Determine whether it is a file path or direct content
    is_task_file = os.path.exists(task_str)

    # When using a temporary file in dispatch mode, tmux and file deletion must be handled manually
    # force_dispatch forces dispatch mode (suitable for the temporary file scenario)
    if (is_dispatch_mode and is_task_file) or force_dispatch:
        # Construct the tmux split-window command
        import shlex

        # Get the current working directory
        cwd = os.getcwd()

        # Do not use shlex.quote; wrap the path directly in double quotes
        quoted_cwd = shlex.quote(cwd)
        # For the task file path, use escaping rather than shlex.quote
        quoted_task_file = task_str.replace("'", "'\"'\"'")

        # Construct the command: cd to the working directory and execute hjb
        # Note: do not automatically delete the task file, to avoid it being mistakenly deleted by the cleanup mechanism
        # Note: do not use the -d parameter, because hjbd has already created a panel via dispatch_command_to_panel
        command = f"cd {quoted_cwd} && hjb -n --task-file '{quoted_task_file}'"

        try:
            # Use the smart dispatch function to create a tmux panel
            from haijunbot.haijunbot_utils.tmux_wrapper import dispatch_command_to_panel

            session_name = dispatch_command_to_panel(
                command,
                stay_in_session_after_exit=stay_in_session_after_exit,
                shell_fallback=True,
            )
            if not session_name:
                PrettyOutput.auto_print("❌ Error: dispatch mode failed to create a tmux panel")
                sys.exit(1)

            # The parent process exits without waiting for the child process to complete
            sys.exit(0)
        except subprocess.CalledProcessError as e:
            PrettyOutput.auto_print(f"❌ Failed to execute the tmux command: {e}")
            sys.exit(1)
        except Exception as e:
            PrettyOutput.auto_print(f"❌ dispatch failed: {e}")
            sys.exit(1)
    else:
        # Non-dispatch mode or non-file mode: use the original logic
        if is_task_file:
            # If it is a file path, use the --task-file parameter
            cmd = ["hjb", "-n", "--task-file", task_str]
        else:
            # If it is direct content, use the --task parameter
            cmd = ["hjb", "-n", "--task", task_str]
        try:
            # Execute the hjb command directly without capturing output, letting the user see hjb output directly
            result = subprocess.run(cmd)
            sys.exit(result.returncode)
        except FileNotFoundError:
            PrettyOutput.auto_print(
                "❌ Error: the 'hjb' command was not found; please ensure haijunbot is installed correctly"
            )
            sys.exit(1)
        except Exception as e:
            PrettyOutput.auto_print(f"❌ Failed to execute the hjb command: {e}")
            sys.exit(1)


@app.command()
def main(
    task: Optional[str] = typer.Argument(
        None, help="Task content (optional; if not provided, enters interactive mode)"
    ),
) -> None:
    init_env("")
    """HaijunBot Agent Dispatcher - a convenience wrapper for hjb

    Usage:
        hjbd "your task"           # Execute the task directly
        hjbd                      # Enter interactive mode to input a task
    """

    if task:
        # Ensure task is string content rather than a type object
        if isinstance(task, str):
            task_str = task
        elif isinstance(task, ArgumentInfo):  # type: ignore[unreachable]
            # Handle typer's ArgumentInfo object
            task_str = task.default if task.default is not None else ""
        else:
            task_str = str(task) if task is not None else ""

        # Direct mode: pass in the task string
        # Determine whether it is a file path (existing files do not get rules added)
        if not os.path.exists(task_str):
            # Not a file; add builtin_rules at the start of the task
            task_str = "'Built-in rules: <rule:builtin_rules>'\n---\nOriginal request: " + task_str

        # Check whether it contains multiline content (a newline character)
        if "\n" in task_str:
            # Multiline input: create a temporary file
            temp_file_path = _write_task_to_temp_file(task_str)
            run_hjbd_dispatch(temp_file_path, is_dispatch_mode=True, force_dispatch=True)
        else:
            # Single-line input: pass directly
            run_hjbd_dispatch(task_str)
    else:
        # Interactive mode: multiline input (using the enhanced interface of the input module)
        task_content = get_multiline_input_enhanced(
            "Please enter the task content (Ctrl+J/Ctrl+] to confirm, Enter for a newline)"
        )
        if not task_content.strip():
            PrettyOutput.auto_print("ℹ️ No task content entered; exiting")
            sys.exit(0)

        # Add builtin_rules at the start of the task
        task_content = (
            "'Built-in rules: <rule:builtin_rules>'\n---\nOriginal request: " + task_content
        )

        # Create a temporary file
        temp_file_path = _write_task_to_temp_file(task_content)
        run_hjbd_dispatch(temp_file_path, is_dispatch_mode=True, force_dispatch=True)


if __name__ == "__main__":
    app()
