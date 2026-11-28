# -*- coding: utf-8 -*-
"""HaijunBot AI assistant main entry module"""

import json
import logging
import os
import shutil
import subprocess
import sys
from enum import Enum
import threading
from datetime import datetime
from pathlib import Path
from typing import Any
from typing import List
from typing import Optional
from typing import Tuple

import typer
import yaml  # type: ignore[import-untyped]


import haijunbot.haijunbot_utils.utils as jutils
from haijunbot.haijunbot_agent.agent_manager import AgentManager
from haijunbot.haijunbot_agent.builtin_input_handler import builtin_input_handler
from haijunbot.haijunbot_agent.config_editor import ConfigEditor
from haijunbot.haijunbot_agent.rule_share_manager import RuleShareManager
from haijunbot.haijunbot_agent.tool_share_manager import ToolShareManager
from haijunbot.haijunbot_utils.config import get_agent_definition_dirs
from haijunbot.haijunbot_utils.exception_utils import save_exception
from haijunbot.haijunbot_utils.config import get_data_dir
from haijunbot.haijunbot_utils.config import get_roles_dirs
from haijunbot.haijunbot_utils.config import is_auto_resume_session
from haijunbot.haijunbot_utils.config import is_non_interactive
from haijunbot.haijunbot_utils.config import set_config
from haijunbot.haijunbot_utils.fzf import fzf_select
from haijunbot.haijunbot_utils.input import get_single_line_input
from haijunbot.haijunbot_utils.input import user_confirm
from haijunbot.haijunbot_utils.output import PrettyOutput
from haijunbot.haijunbot_utils.utils import decode_output
from haijunbot.haijunbot_utils.utils import init_env
from haijunbot.haijunbot_utils.tmux_wrapper import check_and_launch_tmux
from haijunbot.haijunbot_utils.tmux_wrapper import dispatch_to_tmux_window
import haijunbot.haijunbot_utils.globals as jglobals

# Import the quick_config module for the --quick-config option
from haijunbot.haijunbot_utils import quick_config as qc

# Import the hjk module for the --check option
from haijunbot.haijunbot_hjk.core import ToolChecker
from haijunbot.haijunbot_hjk.eli import (
    _install_missing_tools,
    _print_results,
    _perform_check,
)

logger = logging.getLogger(__name__)


# ========== Agent status management ==========
class AgentStatus(Enum):
    """Agent status enum.

    Status descriptions:
    - RUNNING: the agent is running (including executing tasks and idle waiting for commands) - default status
    - WAITING_MULTI: the agent needs multi-line input (such as code)
    - WAITING_SINGLE: the agent needs single-line confirmation (such as whether to continue)
    - WAITING_CONFIRM: the agent is waiting for user confirmation (such as whether to continue)
    """

    RUNNING = "running"  # Running (default status)
    WAITING_MULTI = "waiting_multi"  # Waiting for multi-line input
    WAITING_SINGLE = "waiting_single"  # Waiting for single-line confirmation
    WAITING_CONFIRM = "waiting_confirm"  # Waiting for confirmation


class AgentStateManager:
    """Agent state manager (thread-safe)."""

    def __init__(self):
        self._status = AgentStatus.RUNNING  # Initial status: running
        self._current_mode = None  # Current ARCHER workflow stage
        self._lock = threading.Lock()

    def get_status(self) -> str:
        """Get the current status."""
        with self._lock:
            return self._status.value

    def set_status(self, status: AgentStatus) -> None:
        """Set the current status."""

        with self._lock:
            self._status = status

    def set_running(self) -> None:
        """Set to the running status."""
        self.set_status(AgentStatus.RUNNING)

    def get_mode(self) -> Optional[str]:
        """Get the current ARCHER workflow stage."""
        with self._lock:
            return self._current_mode

    def set_mode(self, mode: Optional[str]) -> None:
        """Set the current ARCHER workflow stage."""
        with self._lock:
            self._current_mode = mode

    def set_waiting_multi(self) -> None:
        """Set to the waiting-for-multi-line-input status."""
        self.set_status(AgentStatus.WAITING_MULTI)

    def set_waiting_single(self) -> None:
        """Set to the waiting-for-single-line-input status."""
        self.set_status(AgentStatus.WAITING_SINGLE)

    def set_waiting_confirm(self) -> None:
        """Set to the waiting-for-user-confirmation status."""
        self.set_status(AgentStatus.WAITING_CONFIRM)


# Global state manager instance
_agent_status_manager: Optional[AgentStateManager] = None


def get_agent_status_manager() -> AgentStateManager:
    """Get the global Agent state manager instance."""
    global _agent_status_manager
    if _agent_status_manager is None:
        _agent_status_manager = AgentStateManager()
    return _agent_status_manager


# ========== Agent status management end ==========


def _normalize_backup_data_argv(argv: List[str]) -> None:
    """
    Compatibility for legacy Click/Typer differences in parsing optional arguments:
    If the user provides only --backup-data with no argument, inject the default directory before parsing.
    """
    try:
        i = 0
        while i < len(argv):
            tok = argv[i]
            if tok == "--backup-data":
                # Case 1: at the end, no argument
                # Case 2: the next token is another option (starting with '-'), indicating no argument was provided
                if i == len(argv) - 1 or (
                    i + 1 < len(argv) and argv[i + 1].startswith("-")
                ):
                    argv.insert(i + 1, "~/haijunbot_backups")
                    i += 1  # Skip the default value we inserted to avoid duplicate insertion
            i += 1
    except Exception:
        # Silently ignore any exception to avoid affecting the main flow
        pass


_normalize_backup_data_argv(sys.argv)

app = typer.Typer(help="HaijunBot AI assistant")


def print_commands_overview() -> None:
    """Print the command and shortcut overview table."""
    try:
        md_content = """## HaijunBot Commands and Shortcuts

| Command | Shortcut | Description |
|---------|----------|-------------|
| haijunbot | hjb | General-purpose AI agent, suitable for various tasks (supports --quick-config for quick LLM configuration) |
| haijunbot-agent | ha | Basic AI agent functionality, handling sessions and tasks |
| haijunbot-agent-dispatcher | hjbd | A convenient wrapper for hjb, supporting task dispatch and interactive mode |
| haijunbot-code-agent | hca | A code agent focused on code analysis, modification, and generation |
| haijunbot-code-agent-dispatcher | hcad | A convenient wrapper for hca, supporting task dispatch and interactive mode |
| haijunbot-git-commit | hgc | Automatically analyzes code changes and generates standardized Git commit messages |
| haijunbot-git-squash | hgs | A Git commit history organization tool |
| haijunbot-config | hcfg | Configuration management tool that dynamically generates configuration web pages based on JSON Schema |
| haijunbot-quick-config | hqc | Quickly configure LLM platforms |
| haijunbot-lsp | hlsp | LSP language server |
| haijunbot-browser | hb | Browser automation |
| haijunbot-windows | hw | Windows GUI automation |
| haijunbot-rules-index | hri | Rule index management |
| haijunbot-platform-manager | hpm | Manage and test different large language model platforms |
| haijunbot-tool | ht | Tool management and invocation system |
| haijunbot-smart-shell | hss | Experimental intelligent Shell functionality |
| haijunbot-sec | hsec | Security analysis suite, combining heuristic scanning and AI deep verification |
| haijunbot-c2rust | hc2r | C→Rust migration suite, supporting progressive migration and intelligent library replacement |
| haijunbot-memory-organizer | hmo | Memory management tool, supporting organizing, merging, and importing/exporting memories |
"""
        PrettyOutput.print_markdown(md_content, title="Command and Shortcut Overview")
    except Exception:
        # Silently ignore rendering exceptions to avoid affecting the main flow
        pass


def handle_edit_option(edit: bool, config_file: Optional[str]) -> bool:
    """Handle the config file editing option, returning whether it was handled and should exit early."""
    if edit:
        ConfigEditor.edit_config(config_file)
        return True
    return False


def handle_share_tool_option(share_tool: bool, config_file: Optional[str]) -> bool:
    """Handle the tool sharing option, returning whether it was handled and should exit early."""
    if share_tool:
        init_env("", config_file=config_file)  # Initialize config but do not show the welcome message
        tool_manager = ToolShareManager()
        tool_manager.run()
        return True
    return False


def handle_share_rule_option(share_rule: bool, config_file: Optional[str]) -> bool:
    """Handle the rule sharing option, returning whether it was handled and should exit early."""
    if share_rule:
        init_env("", config_file=config_file)  # Initialize config but do not show the welcome message
        rule_manager = RuleShareManager()
        rule_manager.run()
        return True
    return False


def handle_interactive_config_option(
    interactive_config: bool, config_file: Optional[str]
) -> bool:
    """Handle the interactive configuration option, returning whether it was handled and should exit early.

    Directly invoke the hcfg command to start the web configuration interface.
    """
    if not interactive_config:
        return False
    try:
        PrettyOutput.auto_print("ℹ️ Starting the web configuration interface...")

        # Build the hcfg command
        cmd = ["hcfg", "--port", "9312"]
        if config_file is not None:
            cmd.extend(["--output", config_file])

        # Directly invoke the hcfg command
        subprocess.run(cmd)
        return True
    except Exception as e:
        PrettyOutput.auto_print(f"❌ Failed to start the configuration interface: {e}")
        return True


def handle_quick_config_option(quick_config: bool) -> bool:
    """Handle the quick configuration option, returning whether it was handled and should exit early.

    Start the quick configuration wizard: quickly configure LLM platform information.
    """
    if not quick_config:
        return False
    qc.quick_config()
    return True


def handle_check_mode(
    check: bool,
    check_lint: bool,
    check_build: bool,
    check_tool_name: Optional[str],
    check_json: bool,
) -> bool:
    """Handle the tool check mode, returning whether it was handled and should exit early.

    Perform tool checks (the original hjk command functionality).
    """
    # Any check-related parameter triggers the check
    is_check_mode = check or check_lint or check_build or check_tool_name is not None

    if not is_check_mode:
        return False

    # Check option mutual exclusivity
    check_flags = [check_lint, check_build]
    active_flags = sum(check_flags)
    if active_flags > 1:
        PrettyOutput.auto_print(
            "❌ Error: --check-lint and --check-build options cannot be used together"
        )
        raise typer.Exit(code=1)

    # Determine the check type
    do_check_lint = check_lint
    do_check_build = check_build

    # Perform the tool check
    checker = ToolChecker()
    results, summary = _perform_check(
        checker, check_tool_name, do_check_lint, do_check_build
    )

    if check_json:
        # JSON format output
        output = {
            "summary": summary,
            "results": results,
        }
        PrettyOutput.auto_print(
            "📝 " + json.dumps(output, ensure_ascii=False, indent=2),
            lang="json",
        )
    else:
        # Friendly text output
        # If there are tools not installed, ask whether to auto-install
        if summary["missing"] > 0:
            _install_missing_tools(results)
            # Re-check tool status
            results, summary = _perform_check(
                checker, check_tool_name, do_check_lint, do_check_build
            )

        # Output the final result
        _print_results(results, summary)

    # If any tool is not installed, return a non-zero exit code
    if summary["missing"] > 0:
        raise typer.Exit(code=1)

    return True


def handle_backup_option(backup_dir_path: Optional[str]) -> bool:
    """Handle the data backup option, returning whether it was handled and should exit early."""
    if backup_dir_path is None:
        return False

    init_env("", config_file=None)
    data_dir = Path(get_data_dir())
    if not data_dir.is_dir():
        PrettyOutput.auto_print(f"❌ Data directory does not exist: {data_dir}")
        return True

    backup_dir_str = backup_dir_path if backup_dir_path.strip() else "~/haijunbot_backups"
    backup_dir = Path(os.path.expanduser(backup_dir_str))
    backup_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file_base = backup_dir / f"haijunbot_data_{timestamp}"

    try:
        archive_path = shutil.make_archive(
            str(backup_file_base), "zip", root_dir=str(data_dir)
        )
        PrettyOutput.auto_print(f"✅ Data successfully backed up to: {archive_path}")
    except Exception as e:
        PrettyOutput.auto_print(f"❌ Data backup failed: {e}")

    return True


def handle_restore_option(
    restore_path: Optional[str], config_file: Optional[str]
) -> bool:
    """Handle the data restore option, returning whether it was handled and should exit early."""
    if not restore_path:
        return False

    restore_file = Path(os.path.expanduser(os.path.expandvars(restore_path)))
    # Support ~ and environment variables, to avoid not finding the file due to an unexpanded path
    if not restore_file.is_file():
        PrettyOutput.auto_print(f"❌ The specified restore file does not exist: {restore_file}")
        return True

    # Do not trigger full environment initialization when restoring data, to avoid the bootstrap flow or network requests
    # Prefer parsing data_path from the config file, otherwise fall back to the default data directory
    data_dir_str: Optional[str] = None
    try:
        if config_file:
            cfg_path = Path(os.path.expanduser(os.path.expandvars(config_file)))
            if cfg_path.is_file():
                with open(cfg_path, "r", encoding="utf-8", errors="ignore") as cf:
                    cfg_data = yaml.safe_load(cf) or {}
                if isinstance(cfg_data, dict):
                    val = cfg_data.get("data_path")
                    if isinstance(val, str) and val.strip():
                        data_dir_str = val.strip()
    except Exception:
        data_dir_str = None

    if not data_dir_str:
        data_dir_str = get_data_dir()

    data_dir = Path(os.path.expanduser(os.path.expandvars(str(data_dir_str))))

    if data_dir.exists():
        if not user_confirm(
            f"Data directory '{data_dir}' already exists; the restore operation will overwrite it. Continue?", default=False
        ):
            PrettyOutput.auto_print("ℹ️ Restore operation cancelled.")
            return True
        try:
            shutil.rmtree(data_dir)
        except Exception as e:
            PrettyOutput.auto_print(f"❌ Unable to remove the existing data directory: {e}")
            return True

    try:
        data_dir.mkdir(parents=True)
        shutil.unpack_archive(str(restore_file), str(data_dir), "zip")
        PrettyOutput.auto_print(f"✅ Data successfully restored from '{restore_path}' to '{data_dir}'")

    except Exception as e:
        PrettyOutput.auto_print(f"❌ Data restore failed: {e}")

    return True


def preload_config_for_flags(config_file: Optional[str]) -> None:
    """Preload the config (only to read feature flags); it will not show the welcome message or affect the subsequent init_env."""
    try:
        jutils.g_config_file = config_file
        jutils.load_config()
    except Exception:
        # Silently ignore config loading exceptions
        pass


def try_switch_to_jca_if_git_repo(
    llm_group: Optional[str],
    tool_group: Optional[str],
    config_file: Optional[str],
    restore: bool,
    restore_session: Optional[str],
    task: Optional[str],
    keep_hjb: bool = False,
    quick_mode: bool = False,
) -> None:
    """Automatically detect a Git repository before initializing the environment, and automatically switch to code development mode (hca)."""
    # Skip code mode auto-switching in non-interactive mode
    if is_non_interactive():
        return
    # If the --keep-hjb parameter is specified, skip auto-switching
    if keep_hjb:
        return
    try:
        res = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=False,
        )
        if res.returncode == 0:
            git_root = decode_output(res.stdout).strip()
            if git_root and os.path.isdir(git_root):
                PrettyOutput.auto_print(f"ℹ️ Detected that the current directory is inside a Git repository: {git_root}")
                PrettyOutput.auto_print(
                    "ℹ️ Automatically switching to 'hca' (haijunbot-code-agent) to enter code development mode..."
                )
                # Build and switch to the haijunbot-code-agent command, passing compatible parameters
                args = ["haijunbot-code-agent"]
                if llm_group:
                    args += ["-g", llm_group]
                if tool_group:
                    args += ["-G", tool_group]
                if config_file:
                    args += ["-f", config_file]
                if restore:
                    args += ["--restore"]  # Interactively select a session to restore
                if restore_session:
                    args += ["--restore-session", restore_session]  # Specify the session file path
                if task:
                    args += ["-T", task]
                if quick_mode:
                    args += ["-q"]
                os.execvp(args[0], args)
    except Exception:
        # Silently ignore detection exceptions, without affecting the main flow
        pass


def handle_builtin_config_selector(
    llm_group: Optional[str],
    tool_group: Optional[str],
    config_file: Optional[str],
    task: Optional[str],
    skip_selector: bool = False,
) -> None:
    """Before entering the default general agent, list built-in configurations for selection (agent/roles).

    Args:
        skip_selector: whether to skip the config selector and directly use the default general agent
    """
    if skip_selector:
        try:
            # Find available builtin directories (support multiple candidates)
            builtin_dirs: List[Path] = []
            try:
                from haijunbot.haijunbot_utils.template_utils import _get_builtin_dir

                # Use the helper function to find the builtin directory
                builtin_dir = _get_builtin_dir()
                if builtin_dir is not None:
                    builtin_dirs.append(builtin_dir)
            except Exception as e:
                save_exception(
                    e,
                    module="haijunbot_agent.haijunbot",
                    function="handle_builtin_config_selector",
                )
                pass

            # Backward compatibility: also try to search upward from the file location (development environment)
            try:
                ancestors = list(Path(__file__).resolve().parents)
                for anc in ancestors[:8]:
                    p = anc / "builtin"
                    if p.exists() and p.is_dir():
                        builtin_dirs.append(p)
            except Exception as e:
                save_exception(
                    e,
                    module="haijunbot_agent.haijunbot",
                    function="handle_builtin_config_selector",
                )
                pass

            # Deduplicate while preserving order
            _seen = set()
            _unique: List[Path] = []
            for d in builtin_dirs:
                try:
                    key = str(d.resolve())
                except Exception:
                    key = str(d)
                if key not in _seen:
                    _seen.add(key)
                    _unique.append(d)
            builtin_dirs = _unique
            # Backward compatibility: keep the first candidate as builtin_root
            builtin_root = builtin_dirs[0] if builtin_dirs else None

            categories = [
                ("agent", "haijunbot-agent", "*.yaml"),
                ("roles", "haijunbot-platform-manager", "*.yaml"),
            ]

            options = []
            for cat, cmd, pattern in categories:
                # Build the list of directories to scan: prefer the directories from the config, otherwise fall back to the builtin directory
                search_dirs = []
                try:
                    if cat == "agent":
                        search_dirs.extend(
                            [
                                Path(os.path.expanduser(os.path.expandvars(str(p))))
                                for p in get_agent_definition_dirs()
                                if p
                            ]
                        )
                    elif cat == "roles":
                        search_dirs.extend(
                            [
                                Path(os.path.expanduser(os.path.expandvars(str(p))))
                                for p in get_roles_dirs()
                                if p
                            ]
                        )
                except Exception:
                    # Ignore config reading exceptions
                    pass

                # Append builtin directories (support multiple candidates)
                try:
                    candidates = (
                        builtin_dirs
                        if isinstance(builtin_dirs, list) and builtin_dirs
                        else ([builtin_root] if builtin_root else [])
                    )
                except Exception:
                    candidates = [builtin_root] if builtin_root else []
                for _bd in candidates:
                    if _bd:
                        search_dirs.append(Path(_bd) / cat)

                # Deduplicate and preserve order
                unique_dirs = []
                seen = set()
                for d in search_dirs:
                    try:
                        key = str(Path(d).resolve())
                    except Exception:
                        key = str(d)
                    if key not in seen:
                        seen.add(key)
                        unique_dirs.append(Path(d))

                for dir_path in unique_dirs:
                    if not dir_path.exists():
                        continue
                    for fpath in sorted(dir_path.glob(pattern)):
                        # Parse YAML to get a readable name/description (silently fall back to the file name on failure)
                        name = fpath.stem
                        desc = ""
                        roles_count = 0
                        data = {}
                        try:
                            with open(
                                fpath, "r", encoding="utf-8", errors="ignore"
                            ) as fh:
                                data = yaml.safe_load(fh) or {}
                            if isinstance(data, dict):
                                name = data.get("name") or data.get("title") or name
                                desc = data.get("description") or data.get("desc") or ""
                                if cat == "roles" and isinstance(
                                    data.get("roles"), list
                                ):
                                    roles_count = len(data["roles"])
                                    if not desc:
                                        desc = f"{roles_count} roles"
                        except Exception:
                            # Ignore parsing errors and use the default display
                            pass

                        # Build detailed information for roles (the name and description of each role)
                        details = ""
                        if cat == "roles":
                            roles = (data or {}).get("roles", [])
                            if isinstance(roles, list):
                                lines = []
                                for role in roles:
                                    if isinstance(role, dict):
                                        rname = str(role.get("name", "") or "")
                                        rdesc = str(role.get("description", "") or "")
                                        lines.append(
                                            f"{rname} - {rdesc}" if rdesc else rname
                                        )
                                details = "\n".join([ln for ln in lines if ln])
                            # If there is no role detail, fall back to the statistics information
                            if not details and isinstance(
                                (data or {}).get("roles"), list
                            ):
                                details = f"{len(data['roles'])} roles"

                        options.append(
                            {
                                "category": cat,
                                "cmd": cmd,
                                "file": str(fpath),
                                "name": str(name),
                                "desc": str(desc),
                                "details": str(details),
                                "roles_count": int(roles_count),
                            }
                        )

            if options:
                # Add a default option to skip selection
                options.insert(
                    0,
                    {
                        "category": "skip",
                        "cmd": "",
                        "file": "",
                        "name": "Skip selection (use the default general agent)",
                        "desc": "Press Enter or ESC directly to skip",
                        "details": "",
                        "roles_count": 0,
                    },
                )

                PrettyOutput.auto_print("✅ Available built-in configurations")

                # Build the markdown table
                md_rows = []
                for idx, opt in enumerate(options, 1):
                    category = str(opt.get("category", ""))
                    name = str(opt.get("name", ""))
                    file_path = str(opt.get("file", ""))
                    # The description column shows the config description; for roles also show the role count and list
                    if category == "roles":
                        count = opt.get("roles_count")
                        details_val = opt.get("details", "")
                        parts: List[str] = []
                        if isinstance(count, int) and count > 0:
                            parts.append(f"{count} roles")
                        if isinstance(details_val, str) and details_val:
                            parts.append(details_val)
                        desc_display = " / ".join(parts) if parts else ""
                    else:
                        desc_display = str(opt.get("desc", ""))
                    md_rows.append(
                        f"| {idx} | {category} | {name} | {file_path} | {desc_display} |"
                    )

                md_content = """## Available Built-in Configurations

| No. | Type | Name | File | Description |
|-----|------|------|------|------|
""" + "\n".join(md_rows)
                PrettyOutput.print_markdown(md_content)

                # Try to use fzf for selection if available (include No. to support number-based filtering)
                fzf_options = [
                    f"{idx:>3} | {opt['category']:<12} | {opt['name']:<30} | {opt.get('desc', '')}"
                    for idx, opt in enumerate(options, 1)
                ]
                selected_str = fzf_select(
                    fzf_options, prompt="Select the configuration number to launch (ESC to skip) > "
                )

                choice_index = -1
                if selected_str:
                    # Try to parse leading number before first '|'
                    try:
                        num_part = selected_str.split("|", 1)[0].strip()
                        selected_index = int(num_part)
                        if 1 <= selected_index <= len(options):
                            choice_index = selected_index - 1
                    except Exception:
                        # Fallback to equality matching if parsing fails
                        for i, fzf_opt in enumerate(fzf_options):
                            if fzf_opt == selected_str:
                                choice_index = i
                                break
                else:
                    # Fallback to manual input if fzf is not used or available
                    choice = get_single_line_input(
                        "Select the configuration number to launch; press Enter directly to use the default general agent (hjb): ",
                        default="",
                    )
                    if choice.strip():
                        try:
                            selected_index = int(choice.strip())
                            if 1 <= selected_index <= len(options):
                                choice_index = selected_index - 1
                        except ValueError:
                            pass  # Invalid input

                if choice_index != -1:
                    try:
                        sel = options[choice_index]
                        # If the "skip" option is chosen, do nothing and proceed to default agent
                        if sel["category"] == "skip":
                            pass
                        else:
                            args: List[str] = []

                            if sel["category"] == "agent":
                                # haijunbot-agent supports -f/--config (global config) and -c/--agent-definition
                                args = [str(sel["cmd"]), "-c", str(sel["file"])]
                                if llm_group:
                                    args += ["-g", str(llm_group)]
                                if config_file:
                                    args += ["-f", str(config_file)]
                                if task:
                                    args += ["--task", str(task)]

                            elif sel["category"] == "roles":
                                # haijunbot-platform-manager role subcommand, supports -c/-t/-g
                                args = [
                                    str(sel["cmd"]),
                                    "role",
                                    "-c",
                                    str(sel["file"]),
                                ]
                                if llm_group:
                                    args += ["-g", str(llm_group)]

                            if args:
                                PrettyOutput.auto_print(f"ℹ️ Launching: {' '.join(args)}")
                                os.execvp(args[0], args)
                    except Exception:
                        # Any exception does not affect the default flow
                        pass
                else:
                    # User pressed Enter or provided invalid input
                    pass
        except Exception:
            # Silently ignore built-in config scanning errors without affecting the main flow
            pass


def _run_with_builtin_handler(
    user_input: str,
    agent: Any,
    output_content_ref: list,
    exit_code_ref: list,
    error_message_ref: list,
) -> Tuple[str, bool]:
    """Use builtin_input_handler to process the input, and return the processed input and whether agent.run needs to be called

    Args:
        user_input: the user input
        agent: the Agent instance
        output_content_ref: the reference list of the output content
        exit_code_ref: the reference list of the exit code
        error_message_ref: the reference list of the error message

    Returns:
        Tuple[str, bool]: (the processed input, whether agent.run needs to be called)
            - ("", True) = builtin handler has handled it; skip agent.run
            - (processed_input, False) = agent.run needs to be called
    """
    processed_input, should_skip_agent = builtin_input_handler(user_input, agent)
    # Mark that the input handler has already run, to avoid running it again in AgentRunLoop
    agent._input_handlers_already_run = True
    if should_skip_agent:
        # builtin handler has finished processing; no need to call agent
        output_content_ref[0] = ""
        exit_code_ref[0] = 0
        error_message_ref[0] = ""
        return "", True  # Skip agent.run
    else:
        return processed_input, False  # Need to call agent.run


@app.callback(invoke_without_command=True)
def run_eli(
    ctx: typer.Context,
    task: Optional[str] = typer.Option(
        None, "-T", "--task", help="Input the task content directly from the command line"
    ),
    task_file: Optional[str] = typer.Option(
        None, "--task-file", help="Read the task content from a file"
    ),
    llm_group: Optional[str] = typer.Option(
        None, "-g", "--llm-group", help="The model group to use, overriding the setting in the config file"
    ),
    tool_group: Optional[str] = typer.Option(
        None, "-G", "--tool-group", help="The tool group to use, overriding the setting in the config file"
    ),
    config_file: Optional[str] = typer.Option(
        None, "-f", "--config", help="Custom config file path"
    ),
    restore: bool = typer.Option(
        False,
        "-r",
        "--restore",
        help="Interactively select a session to restore",
    ),
    restore_session: Optional[str] = typer.Option(
        None,
        "-R",
        "--restore-session",
        help="Restore from the specified session file",
    ),
    edit: bool = typer.Option(False, "-e", "--edit", help="Edit the config file"),
    share_tool: bool = typer.Option(
        False, "--share-tool", help="Share local tools to the central tool repository"
    ),
    share_rule: bool = typer.Option(
        False, "--share-rule", help="Share local rules to the central rule repository"
    ),
    interactive_config: bool = typer.Option(
        False,
        "-I",
        "--interactive-config",
        help="Start the interactive configuration wizard (supplement settings based on the current config)",
    ),
    disable_analysis: bool = typer.Option(
        False,
        "-D",
        "--disable-analysis",
        help="Disable task analysis (overrides the config file setting)",
    ),
    print_prompt: bool = typer.Option(
        False,
        "--print-prompt",
        help="Print prompt information (overrides the config file setting)",
    ),
    backup_data: Optional[str] = typer.Option(
        None,
        "--backup-data",
        help="Back up the HaijunBot data directory. Optionally pass a backup directory. Defaults to '~/haijunbot_backups'",
        show_default=False,
        flag_value="~/haijunbot_backups",
    ),
    restore_data: Optional[str] = typer.Option(
        None, "--restore-data", help="Restore HaijunBot data from the specified archive"
    ),
    non_interactive: bool = typer.Option(
        False,
        "-n",
        "--non-interactive",
        help="Enable non-interactive mode: the user cannot interact with the command, and the script execution timeout is limited to 5 minutes",
    ),
    dispatch: bool = typer.Option(
        False,
        "-d",
        "--dispatch",
        help="Dispatch the task to a new tmux window for execution (only valid in a tmux environment); the current process exits",
    ),
    rule_names: Optional[str] = typer.Option(
        None,
        "--rule-names",
        help="Rule name list (comma-separated), used to load the specified rules",
    ),
    optimize_system_prompt: bool = typer.Option(
        False,
        "-o",
        "--optimize-system-prompt",
        help="Automatically optimize the system prompt: use a large model to optimize the system prompt according to user requirements",
    ),
    quick_mode: bool = typer.Option(
        False,
        "-q",
        "--quick-mode",
        help="Turbo mode: skip methodology loading and rule filtering, etc., and execute the task directly",
    ),
    quick_config: bool = typer.Option(
        False,
        "--quick-config",
        help="Start the quick configuration wizard: quickly configure LLM platform information (Haijun/OpenAI)",
    ),
    # Parameters related to tool checks (the original hjk command functionality)
    # These parameters automatically trigger check mode; no separate --check needs to be added
    check: bool = typer.Option(
        False,
        "--check",
        help="Check the installation status of all tools (the original hjk command)",
    ),
    check_lint: bool = typer.Option(
        False,
        "--check-lint",
        help="Check lint tools (the original hjk --check-lint)",
    ),
    check_build: bool = typer.Option(
        False,
        "--check-build",
        help="Check build tools (the original hjk --check-build)",
    ),
    check_json: bool = typer.Option(
        False,
        "--check-json",
        help="Output the check results in JSON format (used together with other check options)",
    ),
    check_tool_name: Optional[str] = typer.Option(
        None,
        "--check-tool",
        help="Check the specified tool (the original hjk <tool_name>)",
    ),
    skip_config_selector: bool = typer.Option(
        False,
        "-S",
        "--skip-config-selector",
        help="Skip the built-in config selector and directly use the default general agent",
    ),
    keep_hjb: bool = typer.Option(
        False,
        "-k",
        "--keep-hjb",
        help="Prohibit automatically switching to code development mode (hca) and keep using the general agent (hjb)",
    ),
    web_gateway: bool = typer.Option(
        False,
        "--web-gateway",
        help="Enable the Web Gateway service (WebSocket input/output)",
    ),
    web_gateway_port: int = typer.Option(
        8000,
        "--web-gateway-port",
        help="Web Gateway listening port",
    ),
    proxy_node: Optional[str] = typer.Option(
        None,
        "--proxy-node",
        help="The target node ID to which HTTP proxy requests are forwarded",
    ),
    master_url: Optional[str] = typer.Option(
        None,
        "--master-url",
        help="Master node URL, used for HTTP proxy request forwarding",
    ),
    agent_id: Optional[str] = typer.Option(
        None,
        "--agent-id",
        help="Agent ID, a unique identifier assigned by the Web Gateway's AgentManager",
    ),
    new_plugin: Optional[str] = typer.Option(
        None,
        "--new-plugin",
        help="Generate a plugin scaffold: specify the plugin name to generate a complete plugin skeleton conforming to HaijunBot loading conventions",
    ),
    plugin_output_dir: Optional[str] = typer.Option(
        None,
        "--plugin-output-dir",
        help="Plugin scaffold output directory (defaults to the current working directory; used with --new-plugin)",
    ),
    install_plugin: Optional[str] = typer.Option(
        None,
        "--install-plugin",
        help="Install a plugin: specify a plugin directory, archive file path, or http(s) URL (supports .tar, .tar.gz, .tgz, .zip)",
    ),
    install_plugin_force: bool = typer.Option(
        False,
        "--install-plugin-force",
        help="Force overwrite an installed plugin (ignore version comparison; a higher version can overwrite a lower version, and a lower version can also force-overwrite)",
    ),
    upgrade_plugin: Optional[str] = typer.Option(
        None,
        "--upgrade-plugin",
        help="Upgrade a plugin: re-download the latest version of the plugin from its recorded source URL and overwrite the installation (only supports URL-installed plugins)",
    ),
    uninstall_plugin: Optional[str] = typer.Option(
        None,
        "--uninstall-plugin",
        help="Uninstall a plugin: specify the name of the plugin to uninstall",
    ),
    list_plugins_flag: bool = typer.Option(
        False,
        "--list-plugins",
        help="List all installed plugins",
    ),
) -> None:
    """HaijunBot AI assistant command-line interface."""
    if ctx.invoked_subcommand is not None:
        return

    web_gateway_server = None
    thread = None

    # Handle the --quick-config parameter: start the quick configuration wizard
    if handle_quick_config_option(quick_config):
        return

    # Handle tool check parameters (the original hjk command functionality)
    if handle_check_mode(check, check_lint, check_build, check_tool_name, check_json):
        return

    # Handle the plugin scaffold generation parameter
    if new_plugin:
        from haijunbot.haijunbot_agent.utils import scaffold_plugin as do_scaffold_plugin

        result = do_scaffold_plugin(new_plugin, output_dir=plugin_output_dir)
        if result:
            raise typer.Exit(code=0)
        else:
            PrettyOutput.auto_print("❌ Plugin scaffold generation failed")
            raise typer.Exit(code=1)

    # Handle the plugin installation parameter
    if install_plugin:
        from haijunbot.haijunbot_agent.utils import install_plugin as do_install_plugin

        # Record the source URL for URL sources, for use by the upgrade mechanism
        is_url = install_plugin.startswith("http://") or install_plugin.startswith(
            "https://"
        )
        source_url = install_plugin if is_url else None
        success = do_install_plugin(
            install_plugin, force=install_plugin_force, source_url=source_url
        )
        if success:
            PrettyOutput.auto_print("✅ Plugin installed successfully")
            raise typer.Exit(code=0)
        else:
            PrettyOutput.auto_print("❌ Plugin installation failed")
            raise typer.Exit(code=1)

    # Handle the plugin upgrade parameter
    if upgrade_plugin:
        from haijunbot.haijunbot_agent.utils import upgrade_plugin as do_upgrade_plugin

        success = do_upgrade_plugin(upgrade_plugin)
        if success:
            PrettyOutput.auto_print("✅ Plugin upgraded successfully")
            raise typer.Exit(code=0)
        else:
            PrettyOutput.auto_print("❌ Plugin upgrade failed")
            raise typer.Exit(code=1)

    # Handle the plugin uninstall parameter
    if uninstall_plugin:
        from haijunbot.haijunbot_agent.utils import uninstall_plugin as do_uninstall_plugin

        success = do_uninstall_plugin(uninstall_plugin)
        if success:
            PrettyOutput.auto_print(f"✅ Plugin '{uninstall_plugin}' uninstalled successfully")
            raise typer.Exit(code=0)
        else:
            PrettyOutput.auto_print(f"❌ Failed to uninstall plugin '{uninstall_plugin}'")
            raise typer.Exit(code=1)

    # Handle the list-plugins parameter
    if list_plugins_flag:
        from haijunbot.haijunbot_agent.utils import list_plugins as do_list_plugins

        do_list_plugins()
        raise typer.Exit(code=0)

    # Handle task content: prefer reading from a file
    if task and task_file:
        PrettyOutput.auto_print("❌ Error: cannot use both --task and --task-file parameters")
        raise typer.Exit(code=1)

    # Status file path used for tmux parallel tasks
    status_file_path = None

    if task_file:
        try:
            with open(task_file, "r", encoding="utf-8") as file_handle:
                file_content = file_handle.read()

            # Try to parse as JSON to get the status_file field
            try:
                task_data = json.loads(file_content)
                status_file_path = task_data.get("status_file")
                if status_file_path:
                    # Convert status_file_path to a Path object
                    status_file_path = Path(status_file_path)
                # Extract the actual task content
                if "task_desc" in task_data:
                    task = task_data["task_desc"]
                    if "background" in task_data:
                        task += f"\n\nBackground information:\n{task_data['background']}"
                    if "additional_info" in task_data:
                        task += f"\n\nAdditional information:\n{task_data['additional_info']}"
                else:
                    # Not JSON format or no task_desc field; use the file content directly
                    task = file_content
            except json.JSONDecodeError:
                # Not JSON format; use the file content directly
                task = file_content

        except (Exception, FileNotFoundError) as e:
            PrettyOutput.auto_print(f"❌ Error: unable to read task content from file: {str(e)}")
            raise typer.Exit(code=1)

    # No longer print the command list during initialization
    # print_commands_overview()

    # CLI flag: non-interactive mode (does not depend on the config file; used only as an Agent instance attribute)

    # Synchronize other CLI options to the global config to ensure subsequent modules read consistently
    try:
        if llm_group:
            set_config("llm_group", str(llm_group))
        if tool_group:
            set_config("tool_group", str(tool_group))
        if disable_analysis:
            set_config("use_analysis", False)
        if print_prompt:
            set_config("print_prompt", True)
        if proxy_node:
            jglobals.proxy_node = proxy_node
        if master_url:
            jglobals.master_url = master_url
        if agent_id:
            jglobals.agent_id = agent_id

        # Note: the detection of auto_resume_session will be performed after init_env, because config loading is done in init_env
    except Exception:
        # Silently ignore synchronization exceptions, without affecting the main flow
        pass

    # Non-interactive mode requires the task to be passed from the command line
    if non_interactive and not (task and str(task).strip()):
        PrettyOutput.auto_print(
            "❌ Non-interactive mode is enabled: the task content must be passed via --task, because multi-line input is unavailable."
        )
        raise typer.Exit(code=2)

    # Handle the --dispatch parameter: dispatch the task to a new tmux window
    if dispatch:
        if not (task and str(task).strip()):
            PrettyOutput.auto_print(
                "❌ Error: the --dispatch parameter must be used together with the --task parameter"
            )
            raise typer.Exit(code=1)

        PrettyOutput.auto_print("ℹ️ Dispatching the task to a new tmux window...")
        success = dispatch_to_tmux_window(task, sys.argv)
        if success:
            PrettyOutput.auto_print("✅ Task successfully dispatched to a new tmux window")
            raise typer.Exit(code=0)
        else:
            PrettyOutput.auto_print(
                "❌ Dispatch failed: not currently in a tmux environment or tmux is not installed; please use the --dispatch parameter in a tmux environment"
            )
            raise typer.Exit(code=1)

    # Handle data backup
    if handle_backup_option(backup_data):
        return

    # Handle data restore
    if handle_restore_option(restore_data, config_file):
        return

    # Handle config file editing
    if handle_edit_option(edit, config_file):
        return

    # Handle tool sharing
    if handle_share_tool_option(share_tool, config_file):
        return

    # Handle rule sharing
    if handle_share_rule_option(share_rule, config_file):
        return

    # Interactive configuration (supplement settings based on the existing config)
    if handle_interactive_config_option(interactive_config, config_file):
        return

    # Automatically detect a Git repository before initializing the environment, and automatically switch to code development mode (hca)
    # If the -T/--task parameter or the --web-gateway parameter is specified, skip auto-switching
    if not non_interactive and not task and not web_gateway:
        try_switch_to_jca_if_git_repo(
            llm_group,
            tool_group,
            config_file,
            restore,
            restore_session,
            task,
            keep_hjb,
            quick_mode,
        )

    # Before entering the default general agent, list built-in configurations for selection (agent/multi_agent/roles)
    try:
        from haijunbot.haijunbot_utils import utils

        # Set the global config file path (consistent with the logic in init_env)
        utils.g_config_file = config_file
        # Load the config file
        utils.load_config()
    except Exception:
        # Fail silently, without affecting the main flow
        pass

    # Before entering the default general agent, list built-in configurations for selection (agent/multi_agent/roles)
    # Skip built-in role/config selection in non-interactive mode
    # If the -T/--task parameter is specified, skip config selection
    if not non_interactive and not task:
        handle_builtin_config_selector(
            llm_group, tool_group, config_file, task, skip_config_selector
        )

    # Detect tmux and launch it if needed (after argument parsing)
    # Pass config_file so that the config can be loaded before the check
    check_and_launch_tmux(config_file=config_file)

    # Initialize the environment (pass llm_group to ensure the welcome panel shows the correct model group)
    init_env(
        """Welcome to the HaijunBot AI assistant; your intelligent assistant is ready!""",
        config_file=config_file,
        llm_group=llm_group,
    )

    # Detect whether to auto-resume the session after init_env (config already loaded)
    try:
        auto_resume_result = is_auto_resume_session()
        if restore_session is not None or auto_resume_result:
            set_config("restore_session", True)
            # If the user uses --restore-session without an argument, keep restore_session as None
            # If the user specified a file path, check whether the file exists
            if restore_session is not None and restore_session != "":
                if not os.path.exists(restore_session):
                    PrettyOutput.auto_print(f"❌ Session file does not exist: {restore_session}")
                    return
    except Exception:
        # Silently ignore exceptions, without affecting the main flow
        pass

    if web_gateway:
        try:
            import threading

            import uvicorn

            from haijunbot.haijunbot_web_gateway.app import create_app
            from haijunbot.haijunbot_web_gateway.app import set_status_update_callback

            # Token authentication
            auth_token = os.environ.get("HAIJUNBOT_AUTH_TOKEN")
            if auth_token:
                print("[AGENT] Using HAIJUNBOT_AUTH_TOKEN for authentication")

            # Get the status manager and register the status update callback
            status_manager = get_agent_status_manager()

            def on_status_update(status_str: str) -> None:
                """Status update callback when the Web Gateway requests input."""
                # Update the status according to status_str
                if status_str == "running":
                    status_manager.set_running()
                elif status_str == "waiting_multi":
                    status_manager.set_waiting_multi()
                elif status_str == "waiting_single":
                    status_manager.set_waiting_single()
                elif status_str == "waiting_confirm":
                    status_manager.set_waiting_confirm()

            # Register the callback
            set_status_update_callback(on_status_update)

            # Create a custom FastAPI app and add a status query endpoint
            from fastapi import FastAPI, Request
            from fastapi.responses import JSONResponse
            from haijunbot.haijunbot_utils.globals import get_current_agent

            custom_app = FastAPI()

            @custom_app.get("/status")
            async def get_status():
                """Get the Agent running status (task level)."""
                from haijunbot.haijunbot_utils.globals import get_current_agent

                agent = get_current_agent()
                return {
                    "execution_status": status_manager.get_status(),
                    "status": "running",  # Agent process status (always returns running, because the process is still running)
                    "non_interactive": bool(getattr(agent, "non_interactive", False))
                    if agent
                    else False,
                }

            @custom_app.post("/exit_non_interactive")
            async def exit_non_interactive():
                """Exit non-interactive mode without interrupting the current conversation execution."""
                from haijunbot.haijunbot_utils.globals import get_current_agent

                agent = get_current_agent()
                if agent is None:
                    return {"success": False, "error": "No active agent"}
                try:
                    agent.set_non_interactive(False)
                    return {"success": True, "message": "Exited non-interactive mode"}
                except Exception as e:
                    return {"success": False, "error": str(e)}

            @custom_app.get("/diff")
            async def get_diff_api() -> dict:
                """Get the diff (if the working directory is a git repository, return the diff of uncommitted changes in the working tree)."""
                try:
                    is_git_repo = subprocess.run(
                        ["git", "rev-parse", "--is-inside-work-tree"],
                        capture_output=True,
                        text=False,
                    )
                    if (
                        is_git_repo.returncode == 0
                        and is_git_repo.stdout.strip() == b"true"
                    ):
                        diff_result = subprocess.run(
                            ["git", "diff"],
                            capture_output=True,
                            text=False,
                        )
                        if diff_result.returncode == 0:
                            diff_content = diff_result.stdout.decode(
                                "utf-8", errors="replace"
                            )
                            from haijunbot.haijunbot_code_agent.diff_visualizer import (
                                parse_diff_to_structured_data,
                            )

                            structured_data = parse_diff_to_structured_data(
                                diff_content
                            )
                            return {"diff": diff_content, "files": structured_data}
                except Exception:
                    pass
                return {"diff": "", "files": []}

            @custom_app.get("/rules")
            async def get_rules_api() -> dict:
                """Get rule information (overall and loaded)."""
                from haijunbot.haijunbot_web_gateway.common_endpoints import get_rules_info

                return get_rules_info()

            @custom_app.get("/tools")
            async def get_tools_api() -> dict:
                """Get tool information (all tools and allowed tools)."""
                from haijunbot.haijunbot_web_gateway.common_endpoints import get_tools_info

                return get_tools_info()

            @custom_app.get("/sessions")
            async def list_sessions():
                """Get the list of restorable sessions."""
                try:
                    agent = get_current_agent()
                    if agent is None:
                        return {"success": False, "error": "No active agent"}

                    # Parse the session files
                    sessions = agent.session._parse_session_files()

                    # Format the return value
                    session_list = []
                    for (
                        session_file,
                        timestamp,
                        session_name,
                        commit_status,
                    ) in sessions:
                        session_list.append(
                            {
                                "file": session_file,
                                "timestamp": timestamp,
                                "name": session_name,
                                "commit_status": commit_status,
                            }
                        )

                    return {"success": True, "data": session_list}
                except Exception as e:
                    return {"success": False, "error": str(e)}

            @custom_app.post("/sessions")
            async def do_restore_session(request: dict):
                """Restore the specified session."""
                try:
                    session_file = request.get("session_file")
                    if not session_file:
                        return {"success": False, "error": "session_file is required"}

                    agent = get_current_agent()
                    if agent is None:
                        return {"success": False, "error": "No active agent"}

                    # Read the session name
                    session_name = agent.session._read_session_name(session_file)

                    # Restore the session
                    result = agent.session.restore_session_from_file(
                        session_file, session_name
                    )

                    if result:
                        # Set the first flag to False
                        agent.first = False
                        return {
                            "success": True,
                            "data": {
                                "session_file": session_file,
                                "session_name": session_name,
                            },
                        }
                    else:
                        return {"success": False, "error": "Failed to restore session"}
                except Exception as e:
                    return {"success": False, "error": str(e)}

            @custom_app.post("/sessions/save")
            async def save_session():
                """Save the current session and return the file path."""
                try:
                    from haijunbot.haijunbot_utils.globals import (
                        global_agents,
                        running_agent_stack,
                    )

                    # Get the root agent (the first in running_agent_stack, i.e., the earliest-started agent)
                    if not running_agent_stack:
                        return {"success": False, "error": "No active agent"}

                    root_agent_name = running_agent_stack[0]
                    agent = global_agents.get(root_agent_name)

                    if agent is None:
                        return {"success": False, "error": "No active agent"}

                    # Call the save_session method of session_manager
                    result = agent.session.save_session()
                    if result:
                        # Get the saved session file path
                        session_file = agent.session.last_restored_session or ""
                        return {
                            "success": True,
                            "session_file": session_file,
                            "message": "Session saved successfully",
                        }
                    else:
                        return {"success": False, "error": "Failed to save session"}
                except Exception as e:
                    return {"success": False, "error": str(e)}

            @custom_app.post("/update_token")
            async def update_token(request: Request):
                """Update the Agent's authentication Token.

                When the master gateway restarts and the Token changes, the sub-gateway notifies the Agent to update the Token via this endpoint.

                Args:
                    token: the new authentication Token

                Returns:
                    dict: the operation result
                """
                try:
                    # Skip verification when the gateway restarts to synchronize the Token (X-Internal-Sync marker, limited to local 127.0.0.1 requests)
                    if request.headers.get("X-Internal-Sync") == "true":
                        body = await request.json()
                        new_token = body.get("token")
                        if new_token:
                            os.environ["HAIJUNBOT_AUTH_TOKEN"] = new_token
                            logger.info("Auth token updated via internal sync")
                            return {"success": True}
                        return {"success": False, "error": "token is required"}

                    # Verify the Authorization Bearer token
                    auth_header = request.headers.get("Authorization", "")
                    current_token = os.environ.get("HAIJUNBOT_AUTH_TOKEN", "")
                    if not auth_header or not auth_header.startswith("Bearer "):
                        return JSONResponse(
                            status_code=401,
                            content={"success": False, "error": "unauthorized"},
                        )
                    if auth_header[7:] != current_token:
                        return JSONResponse(
                            status_code=401,
                            content={"success": False, "error": "invalid token"},
                        )

                    body = await request.json()
                    new_token = body.get("token")
                    if not new_token:
                        return {"success": False, "error": "token is required"}

                    os.environ["HAIJUNBOT_AUTH_TOKEN"] = new_token
                    logger.info("Auth token updated via /update_token endpoint")
                    return {"success": True}
                except Exception as e:
                    logger.error("Failed to update token: %s", e)
                    return {"success": False, "error": str(e)}

            @custom_app.post("/message")
            async def receive_message(request: dict):
                """Receive a message and add it to the input buffer.

                Args:
                    sender_id: the sender ID
                    content: the message content

                Returns:
                    dict: the operation result
                """
                try:
                    sender_id = request.get("sender_id")
                    content = request.get("content")

                    if not content:
                        return {"success": False, "error": "content is required"}

                    # Build the message format: Agent xxxx sent a message: yyyyy
                    if sender_id:
                        message = f"Agent {sender_id} sent a message: {content}"
                    else:
                        message = f"Agent sent a message: {content}"

                    # If the Agent is waiting for input, inject it directly into the input stream for instant delivery
                    if jglobals.input_inject_callback is not None:
                        jglobals.input_inject_callback(message)
                        delivered = "instant"
                    else:
                        # Otherwise store it in the buffer and wait for the next loop iteration to consume it
                        jglobals.input_buffer.append(message)
                        delivered = "buffered"

                    # Print the received message to the terminal
                    PrettyOutput.auto_print(f"[Message received] {message}")

                    return {
                        "success": True,
                        "data": {
                            "sender_id": sender_id,
                            "content": content,
                            "delivered": delivered,
                        },
                    }
                except Exception as e:
                    return {"success": False, "error": str(e)}

            # Pass the custom app to the gateway
            # Set an environment variable to identify the Agent process
            os.environ["IS_AGENT_PROCESS"] = "1"
            config = uvicorn.Config(
                create_app(custom_app),
                host="127.0.0.1",
                port=web_gateway_port,
                log_level="info",
            )
            web_gateway_server = uvicorn.Server(config)
            thread = threading.Thread(target=web_gateway_server.run, daemon=False)
            thread.start()
            print(f"🌐 Web Gateway started: ws://127.0.0.1:{web_gateway_port}/ws")
            # Verify whether the gateway was set successfully
            try:
                from haijunbot.haijunbot_gateway.manager import get_current_gateway

                get_current_gateway()
            except Exception as e:
                save_exception(
                    e, module="haijunbot_agent.haijunbot", function="on_status_update"
                )
                pass
        except Exception as web_gateway_err:
            try:
                from haijunbot.haijunbot_gateway.manager import set_current_gateway

                set_current_gateway(None)
            except Exception as e:
                save_exception(
                    e, module="haijunbot_agent.haijunbot", function="on_status_update"
                )
                pass
            PrettyOutput.auto_print(f"⚠️ Failed to start the Web Gateway: {str(web_gateway_err)}")

    # Synchronize CLI options to the global config after initializing the environment, to avoid being overwritten by init_env
    try:
        if llm_group:
            set_config("llm_group", str(llm_group))
        if tool_group:
            set_config("tool_group", str(tool_group))
        if disable_analysis:
            set_config("use_analysis", False)
        if print_prompt:
            set_config("print_prompt", True)
    except Exception:
        # Silently ignore synchronization exceptions, without affecting the main flow
        pass

    # Run the main flow
    try:
        agent_manager = AgentManager(
            tool_group=tool_group,
            restore_session=True if restore else restore_session,
            use_analysis=False if disable_analysis else None,
            non_interactive=non_interactive,
            allow_savesession=True,
            rule_names=rule_names,
            optimize_system_prompt=optimize_system_prompt,
            quick_mode=quick_mode,
        )

        # Default CLI mode: run the task (may come from --task or interactive input)
        output_content = ""
        exit_code = 0
        error_message = ""
        agent = None

        try:
            # Initialize the agent and run the task, capturing the output
            agent = agent_manager.initialize()

            # Prefer handling a task passed directly from the command line
            if task:
                # First process it through builtin_input_handler
                processed_input, should_skip = _run_with_builtin_handler(
                    task, agent, [output_content], [exit_code], [error_message]
                )
                if not should_skip:
                    output_content = agent.run(processed_input)
                # agent.run() raises typer.Exit, so normally we never reach here
                exit_code = 0
                error_message = ""
            else:
                # Handle a predefined task or interactive input
                from haijunbot.haijunbot_agent.task_manager import TaskManager
                from haijunbot.haijunbot_agent import get_multiline_input
                from haijunbot.haijunbot_utils.config import (
                    is_non_interactive,
                    is_skip_predefined_tasks,
                )

                # Handle predefined tasks (skipped in non-interactive mode; supports config to skip loading; skipped when a task is specified on the command line)
                if (
                    not is_non_interactive()
                    and not is_skip_predefined_tasks()
                    and agent.first
                ):
                    task_manager = TaskManager()
                    tasks = task_manager.load_tasks()
                    if tasks and (selected_task := task_manager.select_task(tasks)):
                        PrettyOutput.auto_print(f"ℹ️ Starting task execution: \n{selected_task}")  # ty: ignore[possibly-unresolved-reference]
                        # First process it through builtin_input_handler
                        processed_input, should_skip = _run_with_builtin_handler(
                            selected_task,  # ty: ignore[possibly-unresolved-reference]
                            agent,
                            [output_content],
                            [exit_code],
                            [error_message],
                        )
                        if not should_skip:
                            output_content = agent.run(processed_input)
                        # agent.run() raises typer.Exit, so normally we never reach here

                # Get user input, looping until it needs to be passed to the agent
                while True:
                    user_input = get_multiline_input("Please enter your task (Ctrl+C to exit)")
                    if not user_input:
                        break
                    # First process it through builtin_input_handler
                    processed_input, should_skip = _run_with_builtin_handler(
                        user_input,
                        agent,
                        [output_content],
                        [exit_code],
                        [error_message],
                    )
                    if should_skip:
                        # builtin handler has finished processing; continue looping to get new input
                        continue
                    else:
                        # Needs to be passed to the agent for processing
                        output_content = agent.run(processed_input)
                        # If the agent returns None (the builtin handler handled it inside agent.run), continue looping
                        if output_content is None:
                            continue
                        # Otherwise exit normally (single-task mode)
                        break

                raise typer.Exit(code=0)
        except typer.Exit:
            # Normal exit; set the success status
            exit_code = 0
            error_message = ""
            # When agent.run() ends normally, output_content should already have a value
        except Exception as exec_err:
            exit_code = 1
            error_message = str(exec_err)
            raise
        finally:
            if agent is not None:
                try:
                    agent.save_session()
                except Exception as e:
                    save_exception(
                        e, module="haijunbot_agent.haijunbot", function="on_status_update"
                    )
                    pass

            if web_gateway_server is not None:
                try:
                    # Set the exit flag to let the uvicorn server shut down gracefully
                    web_gateway_server.should_exit = True
                    # Force exit flag; do not wait for connections to close (to avoid blocking)
                    web_gateway_server.force_exit = True
                    # Wait for the uvicorn thread to end (at most 2 seconds)
                    if thread is not None:
                        thread.join(timeout=2)
                except Exception as e:
                    save_exception(
                        e, module="haijunbot_agent.haijunbot", function="on_status_update"
                    )
                    pass
                try:
                    from haijunbot.haijunbot_gateway.manager import set_current_gateway

                    set_current_gateway(None)
                except Exception as e:
                    save_exception(
                        e, module="haijunbot_agent.haijunbot", function="on_status_update"
                    )
                    pass

            # If it is a tmux parallel task, write the status file
            if status_file_path:
                try:
                    # Write the status file
                    status_data = {
                        "status": "completed" if exit_code == 0 else "failed",
                        "exit_code": exit_code,
                    }
                    status_file_path.write_text(
                        json.dumps(status_data, ensure_ascii=False), encoding="utf-8"
                    )

                    # Write the output file (if it exists)
                    output_file = status_file_path.with_suffix(".output")
                    # Write the captured output content to the file
                    try:
                        # Ensure the output content is a string
                        def _convert_to_string(content):
                            if content is None:
                                return ""
                            try:
                                # Try to serialize; if it fails, convert to a string
                                json.dumps(content)
                                return json.dumps(content, ensure_ascii=False, indent=2)
                            except (TypeError, ValueError):
                                # When serialization is not possible, convert to a string
                                return str(content)

                        output_content_str = _convert_to_string(output_content)
                        output_file.write_text(output_content_str, encoding="utf-8")
                    except Exception as output_err:
                        # If writing the output fails, at least write the error message
                        PrettyOutput.auto_print(
                            f"⚠️ Failed to write the output file: {str(output_err)}"
                        )
                        pass

                    # Write the error file
                    if exit_code != 0 and error_message:
                        error_file = status_file_path.with_suffix(".error")
                        error_file.write_text(error_message, encoding="utf-8")

                    PrettyOutput.auto_print(f"✅ Status file written: {status_file_path}")
                except Exception as status_err:
                    PrettyOutput.auto_print(f"⚠️ Failed to write the status file: {str(status_err)}")

    except typer.Exit:
        raise
    except Exception as err:  # pylint: disable=broad-except
        PrettyOutput.auto_print(f"❌ Initialization error: {str(err)}")
        raise typer.Exit(code=1)


def main() -> None:
    """Application entry point."""
    app()


if __name__ == "__main__":
    main()
