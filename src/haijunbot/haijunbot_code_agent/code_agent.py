"""HaijunBot code agent module.

This module provides the CodeAgent class for handling code modification tasks.
"""

import hashlib
import logging
import os
from datetime import datetime

from haijunbot.haijunbot_utils.output import PrettyOutput

# -*- coding: utf-8 -*-
import subprocess
import sys
from typing import Any, Dict, List, Optional, Union, cast

import typer

from haijunbot.haijunbot_agent import Agent
from haijunbot.haijunbot_platform.content_types import ContentBlock, TextContent
from haijunbot.haijunbot_agent.events import AFTER_TOOL_CALL
from haijunbot.haijunbot_code_agent.build_validation_config import BuildValidationConfig
from haijunbot.haijunbot_code_agent.code_agent_build import BuildValidationManager
from haijunbot.haijunbot_code_agent.code_agent_diff import DiffManager
from haijunbot.haijunbot_code_agent.code_agent_git import GitManager
from haijunbot.haijunbot_code_agent.code_agent_impact import ImpactManager
from haijunbot.haijunbot_code_agent.code_reviewer import CodeReviewer
from haijunbot.haijunbot_code_agent.code_agent_lint import LintManager
from haijunbot.haijunbot_code_agent.code_agent_postprocess import PostProcessManager
from haijunbot.haijunbot_agent.builtin_input_handler import (
    builtin_input_handler,
)
from haijunbot.haijunbot_code_agent.code_agent_prompts import (
    classify_user_request,
    get_system_prompt,
)
from haijunbot.haijunbot_code_agent.code_analyzer import ContextManager
from haijunbot.haijunbot_code_agent.worktree_manager import WorktreeManager
from haijunbot.haijunbot_code_agent.utils import get_project_overview
from haijunbot.haijunbot_utils.config import is_auto_resume_session
from haijunbot.haijunbot_utils.exception_utils import save_exception
from haijunbot.haijunbot_utils.config import is_confirm_before_apply_patch
from haijunbot.haijunbot_utils.config import is_enable_quick_mode
from haijunbot.haijunbot_utils.config import is_enable_request_classification
from haijunbot.haijunbot_utils.config import is_use_analysis
from haijunbot.haijunbot_utils.config import set_config
from haijunbot.haijunbot_utils.git_utils import detect_large_code_deletion
from haijunbot.haijunbot_utils.git_utils import advance_start_commit
from haijunbot.haijunbot_utils.git_utils import find_git_root_and_cd
from haijunbot.haijunbot_utils.git_utils import get_commits_between
from haijunbot.haijunbot_utils.git_utils import get_diff
from haijunbot.haijunbot_utils.git_utils import get_diff_between_commits
from haijunbot.haijunbot_utils.git_utils import get_diff_file_list
from haijunbot.haijunbot_utils.git_utils import get_latest_commit_hash
from haijunbot.haijunbot_utils.git_utils import get_last_commit_reject_reason
from haijunbot.haijunbot_utils.git_utils import handle_commit_workflow
from haijunbot.haijunbot_utils.git_utils import revert_change
from haijunbot.haijunbot_utils.git_utils import reset_confirm_add_new_files_flag
from haijunbot.haijunbot_utils.input import get_multiline_input
from haijunbot.haijunbot_utils.input import user_confirm
from haijunbot.haijunbot_utils.tmux_wrapper import check_and_launch_tmux
from haijunbot.haijunbot_utils.tmux_wrapper import dispatch_to_tmux_window

from haijunbot.haijunbot_utils.utils import _acquire_single_instance_lock
from haijunbot.haijunbot_utils.utils import init_env
from haijunbot.haijunbot_utils.globals import set_current_agent
from haijunbot.haijunbot_utils.globals import clear_current_agent
import haijunbot.haijunbot_utils.globals as jglobals

logger = logging.getLogger(__name__)

app = typer.Typer(help="HaijunBot Code Assistant")


class CodeAgent(Agent):
    """Code modification agent of the HaijunBot system.

    Responsible for handling code analysis, modification, and git operations.
    """

    def __init__(
        self,
        need_summary: bool = True,
        append_tools: Optional[str] = None,
        tool_group: Optional[str] = None,
        non_interactive: Optional[bool] = True,
        rule_names: Optional[str] = None,
        disable_review: bool = False,
        review_max_iterations: int = 0,
        enable_task_list_manager: bool = True,
        optimize_system_prompt: bool = False,
        quick_mode: bool = False,
        **kwargs: Any,
    ) -> None:
        # Store the quick mode flag
        self.quick_mode = quick_mode

        # CodeAgent basic attribute initialization
        self._init_code_agent_base_attributes(
            tool_group, disable_review, review_max_iterations
        )

        # Context management related initialization
        self._init_code_agent_context_managers()

        # Code management related manager initialization
        self._init_code_agent_managers()

        # Tool list construction
        base_tools = self._build_code_agent_tool_list(
            append_tools, enable_task_list_manager
        )

        # Parent class initialization preparation and invocation
        explicit_params = self._prepare_code_agent_parent_init(
            need_summary,
            non_interactive,
            base_tools,
            optimize_system_prompt,
            kwargs,
        )
        super().__init__(**explicit_params, **kwargs)

        # Settings after parent class initialization
        self._setup_code_agent_after_parent_init()

    def get_user_origin_input(self) -> Union[str, List[ContentBlock]]:
        """Get raw user input (CodeAgent override)

        Returns:
            Union[str, List[ContentBlock]]: Raw user input (without CodeAgent enhancement)
        """
        return self._raw_user_input

    def _convert_to_string(self, user_input: Union[str, List[ContentBlock]]) -> str:
        """Convert user input to a string

        Args:
            user_input: User input (plain text or multimodal content)

        Returns:
            str: String representation
        """
        if isinstance(user_input, str):
            return user_input

        # If it is multimodal content, extract the text parts
        text_parts = []
        for block in user_input:
            if isinstance(block, dict) and block.get("type") == "text":
                text_parts.append(block.get("text", ""))

        return "\n".join(text_parts) if text_parts else "[multimodal content]"

    def _append_to_session_prompt(self, content: str) -> None:
        """Safely append content to session.prompt

        Args:
            content: The string content to append
        """
        if isinstance(self.session.prompt, str):
            self.session.prompt += content
        else:
            # If session.prompt is a List[ContentBlock], convert content to TextContent and append
            text_block: TextContent = {"type": "text", "text": content}
            self.session.prompt.append(text_block)

    def _init_code_agent_base_attributes(
        self,
        tool_group: Optional[str],
        disable_review: bool,
        review_max_iterations: int,
    ) -> None:
        """Initialize CodeAgent basic attributes

        Args:
            tool_group: Tool group configuration
            disable_review: Whether to disable code review
            review_max_iterations: Maximum number of code review iterations
        """
        # Set the working directory and tool group configuration
        self.root_dir = os.getcwd()
        self.tool_group = tool_group

        # Review related configuration
        # Note: disable_review only saves the configuration value; whether review is actually executed is determined dynamically at runtime
        self.disable_review = disable_review  # Save the user-configured disable_review value
        self.review_max_iterations = review_max_iterations

        # Git related initialization: store the commit hash at the start, used for subsequent git diff retrieval
        self.start_commit: Optional[str] = None
        # Record the commit hash at the last backup, used to compute incremental backups
        self.last_backup_commit: Optional[str] = None

        # Commit prefix and suffix, used to generate commit messages
        self.prefix: str = ""
        self.suffix: str = ""

        # Save the raw user input (used for session name generation)
        self._raw_user_input: Union[str, List[ContentBlock]] = ""

    def _init_code_agent_context_managers(self) -> None:
        """Initialize CodeAgent context management related components"""
        # Initialize the context manager (used for code analysis and context tracking)
        self.context_manager = ContextManager(self.root_dir)

    def _init_code_agent_managers(self) -> None:
        """Initialize the various managers related to CodeAgent code management"""
        # Git manager: handles Git operations and commits
        self.git_manager = GitManager(self.root_dir)
        # Check whether git username and email are set
        self.git_manager.check_git_config()

        # Diff manager: handles code diff analysis and display
        self.diff_manager = DiffManager(self.root_dir)

        # Impact analysis manager: analyzes the scope of impact of code modifications
        self.impact_manager = ImpactManager(self.root_dir, self.context_manager)

        # Build verification manager: verifies the build state after code modifications
        self.build_validation_manager = BuildValidationManager(self.root_dir)

        # Lint manager: performs static code analysis
        self.lint_manager = LintManager(self.root_dir)

        # Post-processing manager: handles cleanup and optimization after code modifications
        self.post_process_manager = PostProcessManager(self.root_dir)

    def _build_code_agent_tool_list(
        self,
        append_tools: Optional[str],
        enable_task_list_manager: bool,
    ) -> List[str]:
        """Build the CodeAgent tool list

        Args:
            append_tools: The list of tools to append (comma-separated)
            enable_task_list_manager: Whether to enable the task list manager

        Returns:
            List[str]: The constructed tool list
        """
        # Build the base tool list (CodeAgent-specific code operation tools)
        base_tools = [
            "execute_script",  # Script execution tool
            "read_code",  # Code reading tool
            "edit_file",  # Find-and-replace editing tool
            "edit_file_by_line",  # Line-number-based replacement editing tool
            "write_file",  # Whole-file overwrite tool
            "commit",  # Generate a formal commit (automatically squashes CheckPoint temporary commits)
            "load_rule",  # Rule loading tool
            "auto_select_rule",  # Automatic rule selection tool
            "virtual_tty",  # Virtual terminal tool, supports interactive operations
            "search_web",  # Web search tool
            "read_webpage",  # Webpage content reading tool
            "memory",  # Memory management tool (supports save/retrieve/clear operations)
            "symbol_dependency",  # Symbol dependency query tool
            "lsp",  # LSP semantic query tool (definition/references/implementation/diagnostics/fix suggestions)
            "add_images",  # Tool to add images to the conversation context
            "ocr",  # OCR text recognition tool (converts images to text so models that don't support multimodality can read images)
            "gateway_manager",  # Gateway management tool (Agent communication, node management, model group queries, etc.)
            "browser_ext_sessions",  # Browser extension tool - list online sessions
            "browser_ext_capabilities",  # Browser extension tool - list session capability inventory
            "browser_ext_call",  # Browser extension tool - call by capability name
            "daemon_sessions",  # Local daemon tool - list online sessions
            "daemon_capabilities",  # Local daemon tool - list session capability inventory
            "daemon_call",  # Local daemon tool - call by capability name
            "sub_code_agent",  # Sub code Agent tool, used to create sub-Agents to execute independent tasks
            "eval_js",  # Frontend JS execution tool (dispatches JS to the frontend browser in Web gateway mode)
            "haijunbot_frontend",  # HaijunBot frontend tool (notifies the frontend to open files/jump to lines/select code)
            "timer",  # Timer tool (supports after/at/loop scheduled execution, with cancel/list/clear management)
            "hotpatch",  # Arbitrary code hot-patch tool (hot-updates/injects Python module code, takes effect immediately without restart)
        ]
        # If the task list manager is enabled, add the corresponding tool
        if enable_task_list_manager:
            base_tools.append("task_list_manager")  # Task list management tool

        # Process the appended tools (parse from the parameters and deduplicate)
        if append_tools:
            additional_tools = [
                t for t in (tool.strip() for tool in append_tools.split(",")) if t
            ]
            base_tools.extend(additional_tools)
            # Deduplicate while preserving order
            base_tools = list(dict.fromkeys(base_tools))

        # Append plugin tools declared to apply to code_agent (driven by the plugin config's code_agent_tools field, without hardcoding plugin names/tool names)
        from haijunbot.haijunbot_tools.plugin_registry import PluginRegistry

        registry = PluginRegistry.instance()
        for plugin_name in registry.get_code_agent_tool_plugins():
            base_tools.extend(registry.get_plugin_tools(plugin_name))
        # Deduplicate while preserving order
        base_tools = list(dict.fromkeys(base_tools))

        return base_tools

    def _merge_rule_names(self, eli_rule_names: Optional[str]) -> Optional[str]:
        """Merge the config file default rules and command-line rules

        Args:
            eli_rule_names: The rule names passed in from the command line (a comma-separated string)

        Returns:
            Optional[str]: The merged rule names (a comma-separated string); returns None if both are empty
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

        # If neither exists, return None
        if not default_rules and not eli_rules:
            return None

        # Merge and deduplicate
        all_rules = list(dict.fromkeys(default_rules + eli_rules))  # Order-preserving deduplication

        # Convert to a comma-separated string
        return ",".join(all_rules) if all_rules else None

    def _prepare_code_agent_parent_init(
        self,
        need_summary: bool,
        non_interactive: Optional[bool],
        base_tools: List[str],
        optimize_system_prompt: bool,
        kwargs: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Prepare the parameters for CodeAgent parent class initialization

        Args:
            need_summary: Whether a summary is needed
            non_interactive: Whether in non-interactive mode
            base_tools: The base tool list
            optimize_system_prompt: Whether to optimize the system prompt
            kwargs: Other keyword arguments

        Returns:
            Dict[str, Any]: The parameter dictionary prepared to pass to the parent class
        """
        # Get the CodeAgent-specific system prompt
        code_system_prompt = get_system_prompt()

        # Merge the default rules and command-line rules
        eli_rule_names = kwargs.pop("rule_names", None)
        merged_rule_names = self._merge_rule_names(eli_rule_names)

        # Read default values from the config file, allowing overrides via kwargs
        # If not specified in kwargs, read the default value from the config file
        use_methodology = kwargs.pop("use_methodology", True)
        use_analysis = kwargs.pop("use_analysis", is_use_analysis())
        # Save the original use_analysis config value, used to manually invoke analysis before the run method ends
        self._use_analysis_config = use_analysis
        # name uses the passed-in value; if not passed in, uses the default value "CodeAgent"
        name = kwargs.pop("name", "CodeAgent")

        # In quick mode, disable methodology loading and automatic rule selection
        if self.quick_mode:
            use_methodology = False
            enable_auto_rule_select = False
        else:
            # In non-quick mode, set enable_auto_rule_select based on kwargs or the default value
            enable_auto_rule_select = kwargs.pop("enable_auto_rule_select", True)

        # Prepare the parameters to explicitly pass to super().__init__
        # Note: if these parameters are also in kwargs, they need to be removed first to avoid duplicate-passing errors
        explicit_params = {
            "system_prompt": code_system_prompt,
            "name": name,
            "auto_complete": False,
            "need_summary": need_summary,
            "use_methodology": use_methodology,
            "use_analysis": False,  # Do not enable analysis at initialization; manually invoke before the run method ends
            "non_interactive": non_interactive,
            "use_tools": base_tools,
            "optimize_system_prompt": optimize_system_prompt,
            "rule_names": merged_rule_names,
            "enable_auto_rule_select": enable_auto_rule_select,
            "quick_mode": self.quick_mode,  # Pass the quick mode flag to the parent class
        }

        # Automatically remove all explicitly passed parameters to avoid duplicate-passing errors
        # This way, when adding new parameters in the future, as long as they are declared in explicit_params, they will be handled automatically
        for key in explicit_params:
            kwargs.pop(key, None)

        return explicit_params

    def _setup_code_agent_after_parent_init(self) -> None:
        """Settings after CodeAgent parent class initialization"""
        # Set the Agent type identifier
        self._agent_type = "code_agent"

        # Establish the association between CodeAgent and Agent, so tools can obtain the context manager
        self._code_agent = self

        # Subscribe to the post tool-call event, used to handle diff display and commit after code modifications
        self.event_bus.subscribe(AFTER_TOOL_CALL, self._on_after_tool_call)

    def run(
        self,
        user_input: Union[str, List[ContentBlock]],
        prefix: str = "",
        suffix: str = "",
    ) -> Optional[str]:
        """Run the code agent with the given user input.

        Args:
            user_input: The user's requirement/request

        Returns:
            str: Output describing the execution result; returns None on success
        """
        # Flag whether the session should be saved (not saved when built-in command handling completes)
        _should_save_session = True
        # Reset the auto-complete commit flag (skip the duplicate commit here if the AutoComplete path has already committed)
        self._auto_commit_done = False
        try:
            set_current_agent(self.name, self)

            # Save the raw user input (used for session name generation)
            self._raw_user_input = user_input
            self.original_user_input = user_input

            # Store prefix and suffix for use by the commit command
            self.prefix = prefix
            self.suffix = suffix

            # Prioritize handling input processors (such as built-in commands and shell shortcuts)
            # If the current input has already been handled, continue waiting for user input without entering the requirement classification process
            processed_input = ""
            while True:
                # Only handle built-in commands and shell commands when user_input is a string
                if isinstance(user_input, str):
                    processed_input, is_handled = builtin_input_handler(
                        user_input, self
                    )
                    # Mark the input processor as run to avoid running it repeatedly in AgentRunLoop
                    self._input_handlers_already_run = True
                    if is_handled:
                        # If there is returned prompt information, append it to addon_prompt
                        if processed_input:
                            current_addon = self.session.addon_prompt or ""
                            self.set_addon_prompt(
                                f"{current_addon}\n{processed_input}".strip()
                            )
                        # The built-in command handling is complete; continue waiting for user input
                        user_input = get_multiline_input(
                            "Please enter your requirement (Ctrl+C to exit)"
                        )
                        if not user_input:
                            # The user canceled the input; do not save the session
                            _should_save_session = False
                            return None
                        continue

                    if processed_input:
                        user_input = processed_input
                break

            prev_dir = os.getcwd()

            # Requirement classification: only performed on the first run (session not restored)
            # If a session-restore parameter is specified, there is no need to classify the requirement (because the system prompt already exists)
            if self.first:
                # Quick mode: skip task classification, automatic rule loading, context recommendation, and methodology loading
                if self.quick_mode:
                    # Quick mode is enabled; skip the related steps
                    # === Phase 3: Git environment initialization ===
                    self.git_manager.init_env(prefix, suffix, self)
                    # Get the initial commit (after Git environment initialization)
                    start_commit = get_latest_commit_hash()
                    self.start_commit = start_commit
                    # Add the initial commit information to addon_prompt (safe rollback point)
                    if start_commit:
                        initial_commit_prompt = f"""
**🔖 Initial Git Commit (Safe Rollback Point)**:
The initial commit at the start of this task is: `{start_commit}`

**⚠️ Important Note**: If the files are too severely corrupted to recover, you can use the following command to reset to this initial commit:
```bash
git reset --hard {start_commit}
```
This will discard all uncommitted changes and restore the workspace to the state at the start of the task. Use this command with caution and make sure this is what you really want to do.
"""
                        # Append the initial commit information to the existing addon_prompt
                        current_addon = self.session.addon_prompt or ""
                        self.set_addon_prompt(
                            f"{current_addon}\n{initial_commit_prompt}".strip()
                        )

                    # In quick mode, use the user input directly
                    user_input_str = self._convert_to_string(user_input)
                    enhanced_input = user_input_str
                else:
                    # Normal mode: execute all phases
                    # === Phase 1: Requirement classification (only performed when enabled) ===
                    if is_enable_request_classification():
                        self._classify_and_switch_model(
                            user_input, classify_user_request, get_system_prompt
                        )

                    # === Stage 2: Generate non-interactive mode description ===
                    # Generate additional notes based on the current mode, for the LLM to sense the execution strategy
                    non_interactive_note = ""
                    if getattr(self, "non_interactive", False):
                        non_interactive_note = (
                            "\n\n[System Notes]\n"
                            "This session is in **non-interactive mode**:\n"
                            "- In PLAN mode, after giving a clear, executable detailed plan, you should **automatically enter EXECUTE mode to execute the plan**, without waiting for extra user confirmation;\n"
                            '- In EXECUTE mode, keep step-by-step small commits and a rollback strategy, but no need to repeatedly ask the user "whether to continue";\n'
                            "- If information is severely insufficient, you may supplement necessary analysis yourself in RESEARCH mode, instead of getting stuck waiting for user input.\n"
                        )

                    # === Stage 3: Git environment initialization ===
                    self.git_manager.init_env(prefix, suffix, self)
                    # Get the initial commit (after Git environment initialization)
                    start_commit = get_latest_commit_hash()
                    self.start_commit = start_commit
                    # Add initial commit info to addon_prompt (safe rollback point)
                    if start_commit:
                        initial_commit_prompt = f"""
**🔖 Initial Git Commit (safe rollback point)**:
The initial commit at the start of this task is: `{start_commit}`

**⚠️ Important**: If files are badly corrupted and cannot be recovered, you can use the following command to reset to this initial commit:
```bash
git reset --hard {start_commit}
```
This will discard all uncommitted changes and restore the working tree to the state at the start of the task. Please use this command with caution and make sure this is truly the operation you want.
"""
                        # Append initial commit info to the existing addon_prompt
                        current_addon = self.session.addon_prompt or ""
                        self.set_addon_prompt(
                            f"{current_addon}\n{initial_commit_prompt}".strip()
                        )

                    # === Stage 4: Get project overview ===
                    project_overview = get_project_overview(self.root_dir)

                    first_tip = """Please strictly follow the specifications below when performing code modification tasks:
            1. Perform only one step per response; analyze first, then modify, avoiding multiple changes in one step.
            2. Make full use of tools to understand user requirements and existing code; do not make unfounded assumptions.
            3. If you are unsure which files to modify, you must first analyze and find the files that need modification, and edit only after clarifying the target.
            4. For simple text replacements, it is recommended to use the edit_file tool (find and replace) for precise modification. For complex code (over 50 lines or involving multi-file coordination), you must use task_list_manager to create a task list for safe splitting.
            5. For code editing tasks, prefer edit_file's find and replace, ensuring the search text has exactly one precise match in the target file, to guarantee the accuracy and safety of the modification.
            6. If a large-scale rewrite is needed (over 200 lines or involving refactoring), use the write_file tool to overwrite the entire file; if the target line numbers are known, you can use edit_file_by_line to replace by line number range.
            7. If information is unclear, prioritize calling tools to supplement analysis; do not make subjective assumptions.
            8. **Important: Clean up temporary files**: Temporary files generated during development (such as test files, debug scripts, backup files, temporary logs, etc.) must be cleaned up and deleted before committing, otherwise they will be automatically committed to the git repository. If temporary files are created for debugging or testing, they must be deleted immediately after completion.
            """

                    # === Stage 6: Build enhanced input ===
                    # Convert user_input to a string
                    user_input_str = self._convert_to_string(user_input)
                    if project_overview:
                        enhanced_input = (
                            project_overview
                            + "\n\n"
                            + first_tip
                            + non_interactive_note
                            + "\n\nTask description:\n"
                            + user_input_str
                        )
                    else:
                        enhanced_input = (
                            first_tip
                            + non_interactive_note
                            + "\n\nTask description:\n"
                            + user_input_str
                        )

            else:
                # When restoring a session, use the user input directly (context has been restored from the session)
                user_input_str = self._convert_to_string(user_input)
                enhanced_input = user_input_str

            try:
                if self.model:
                    self.model.set_suppress_output(False)
                result = super().run(enhanced_input)
                # Ensure the return value is str or None
                if result is None:
                    result_str = None
                else:
                    result_str = str(result)
            except RuntimeError as e:
                PrettyOutput.auto_print(f"⚠️ Execution failed: {str(e)}")
                return str(e)

            # Handle uncommitted changes
            self.git_manager.handle_uncommitted_changes()

            # Manually call the analysis feature at the end of the task based on configuration (before the final commit)
            if self._use_analysis_config:
                # Ask the user whether analysis is needed; by default no analysis is performed
                default_analyze = bool(self.non_interactive)
                should_analyze = user_confirm(
                    "📊 Analyze this task and generate a methodology?",
                    default=default_analyze,
                )
                if should_analyze:
                    try:
                        self.analysis()
                    except Exception as e:
                        # Analysis failure should not affect the main flow; only log the error
                        PrettyOutput.auto_print(f"⚠️ Task analysis failed: {str(e)}")

            # The auto-complete path has already committed (_execute_auto_complete); avoid duplicate commits here
            if not getattr(self, "_auto_commit_done", False):
                # Final fallback: the user may have committed manually during the task; move the start point forward before confirming the commit
                self._advance_start_commit_if_needed()
                end_commit = get_latest_commit_hash()
                commits = self.git_manager.show_commit_between(
                    self.start_commit, end_commit
                )
                self.git_manager.handle_commit_confirmation(
                    commits,
                    self.start_commit,
                    prefix,
                    suffix,
                    self,
                    self.post_process_manager.post_process_modified_files,
                )

            return result_str

        except RuntimeError as e:
            return f"Error during execution: {str(e)}"
        finally:
            # Unregister the agent at the end of the run method
            # Automatically save session state
            try:
                if _should_save_session:
                    self.save_session()
            except Exception as e:
                # Failure to save the session does not affect other cleanup operations
                PrettyOutput.auto_print(f"⚠️ Failed to save session: {str(e)}")
            clear_current_agent()
            # Normal exit: notify the session daemon to clean up memory (without persisting to disk)
            self._notify_session_daemon_quit()

            # Ensure switching back to the original working directory after CodeAgent completes
            try:
                os.chdir(prev_dir)
            except Exception as e:
                save_exception(e, module="haijunbot_code_agent.code_agent", function="run")
                pass

    def _advance_start_commit_if_needed(self) -> None:
        """If a user manual commit exists, move the task start commit forward to the latest manual commit

        Only temporary commits starting with "CheckPoint #" are considered CodeAgent auto-produced; the rest
        of commits (user manual commits, GitCommitTool formal commits) are all considered manual commits and should serve as
        the new task start point, to avoid subsequent squash / reset accidentally affecting them.
        """
        new_start = advance_start_commit(self.start_commit)
        if new_start and new_start != self.start_commit:
            PrettyOutput.auto_print(
                f"ℹ️ Manual commit detected, task start point updated to {new_start[:7]}"
            )
            self.start_commit = new_start

    def _on_after_tool_call(
        self,
        agent: Agent,
        current_response: Optional[str] = None,
        need_return: Optional[bool] = None,
        tool_prompt: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """Callback function after a tool call."""
        # Reset the global flag to allow file confirmation again in this flow
        reset_confirm_add_new_files_flag()

        # The user may commit manually while the task is in progress; promptly move the task start point forward to avoid accidentally affecting their commit
        self._advance_start_commit_if_needed()

        final_ret = ""
        diff = get_diff()

        if diff:
            start_hash = get_latest_commit_hash()
            modified_files = get_diff_file_list()

            # Use enhanced diff visualization (if available)
            try:
                from haijunbot.haijunbot_code_agent.diff_visualizer import (
                    visualize_diff_enhanced,
                )
                from haijunbot.haijunbot_utils.config import get_diff_show_line_numbers
                from haijunbot.haijunbot_utils.config import get_diff_visualization_mode

                # Show the overall diff (using enhanced visualization)
                visualization_mode = get_diff_visualization_mode()
                show_line_numbers = get_diff_show_line_numbers()
                # Build the file path display (show all file names when there are multiple files)
                file_path_display = ", ".join(modified_files) if modified_files else ""
                visualize_diff_enhanced(
                    diff,
                    file_path=file_path_display,
                    mode=visualization_mode,
                    show_line_numbers=show_line_numbers,
                )
            except ImportError:
                # If the import fails, fall back to the original method
                PrettyOutput.auto_print(diff, lang="diff")
            except Exception as e:
                # If visualization fails, fall back to the original method
                PrettyOutput.auto_print(f"⚠️ Diff visualization failed, using default method: {e}")
                PrettyOutput.auto_print(diff, lang="diff")

            # Update the context manager
            self.impact_manager.update_context_for_modified_files(modified_files)

            # Perform impact scope analysis
            impact_report = self.impact_manager.analyze_edit_impact(modified_files)

            per_file_preview = self.diff_manager.build_per_file_patch_preview(
                modified_files, use_enhanced_visualization=False
            )

            # In all modes, detect large code deletions before committing and ask the large model
            detection_result = detect_large_code_deletion()
            if detection_result is not None:
                # Large code deletion detected; ask the large model whether it is reasonable
                is_reasonable = self.ask_llm_about_large_deletion(
                    detection_result, per_file_preview
                )
                if not is_reasonable:
                    # The large model considers it unreasonable; undo the modification
                    PrettyOutput.auto_print("ℹ️ Modification undone (the large model considers the code deletion unreasonable)")
                    revert_change()
                    final_ret += (
                        "\n\nModification undone (large code deletion detected and the large model judged it unreasonable)\n"
                    )
                    final_ret += f"# Patch preview (by file):\n{per_file_preview}"
                    PrettyOutput.auto_print(final_ret, lang="markdown")  # Keep syntax highlighting
                    self._append_to_session_prompt(final_ret)
                    return

            commited = handle_commit_workflow(start_hash)
            if commited:
                # Get commit info
                end_hash = get_latest_commit_hash()
                commits = get_commits_between(start_hash, end_hash)

                # Add commit info to final_ret (show diff by file; for deleted files only show a hint)
                if commits:
                    # Get the latest commit info (the commits list is in reverse chronological order; the first is the latest)
                    latest_commit_hash, latest_commit_message = commits[0]
                    commit_short_hash = (
                        latest_commit_hash[:7]
                        if len(latest_commit_hash) >= 7
                        else latest_commit_hash
                    )

                    final_ret += (
                        f"\n\nCode modification completed\n"
                        f"✅ Automatically committed\n"
                        f"   Commit ID: {commit_short_hash} ({latest_commit_hash})\n"
                        f"   Commit message: {latest_commit_message}\n"
                        f"\nPatch content (by file):\n{per_file_preview}\n"
                    )

                    # Add impact scope analysis report
                    final_ret = self.impact_manager.handle_impact_report(
                        impact_report, self, final_ret
                    )

                    # Build verification (entry commented out: automatic build verification is disabled)
                    # config = BuildValidationConfig(self.root_dir)
                    # (
                    #     build_validation_result,
                    #     final_ret,
                    # ) = self.build_validation_manager.handle_build_validation(
                    #     modified_files, self, final_ret
                    # )
                    config = BuildValidationConfig(self.root_dir)
                    build_validation_result = None

                    # Static analysis
                    final_ret = self.lint_manager.handle_static_analysis(
                        modified_files, build_validation_result, config, self, final_ret
                    )
                else:
                    # If no commits were obtained, try to get commit info directly from end_hash
                    commit_info = ""
                    if end_hash:
                        try:
                            result = subprocess.run(
                                ["git", "log", "-1", "--pretty=format:%H|%s", end_hash],
                                capture_output=True,
                                text=True,
                                encoding="utf-8",
                                errors="replace",
                                check=False,
                            )
                            if (
                                result.returncode == 0
                                and result.stdout
                                and "|" in result.stdout
                            ):
                                (
                                    commit_hash,
                                    commit_message,
                                ) = result.stdout.strip().split("|", 1)
                                commit_short_hash = (
                                    commit_hash[:7]
                                    if len(commit_hash) >= 7
                                    else commit_hash
                                )
                                commit_info = (
                                    f"\n✅ Automatically committed\n"
                                    f"   Commit ID: {commit_short_hash} ({commit_hash})\n"
                                    f"   Commit message: {commit_message}\n"
                                )
                        except Exception as e:
                            save_exception(
                                e,
                                module="haijunbot_code_agent.code_agent",
                                function="_on_after_tool_call",
                            )
                            pass

                    if commit_info:
                        final_ret += f"\n\nCode modification completed{commit_info}\n"
                    else:
                        final_ret += "\n\nModification did not take effect\n"

                #
                latest_commit_hash = get_latest_commit_hash()
                if self.start_commit and latest_commit_hash:
                    diff_lines = get_diff_between_commits(
                        self.start_commit, latest_commit_hash
                    )
                else:
                    diff_lines = ""
                if diff_lines:
                    assert (
                        self.start_commit is not None and latest_commit_hash is not None
                    )
                    # Use the last backup commit as the start point; if none, use the initial commit
                    backup_start_commit = self.last_backup_commit or self.start_commit
                    commits = get_commits_between(
                        backup_start_commit, latest_commit_hash
                    )

                    # Calculate the incremental changes from the last backup point to now (used for the backup decision)
                    diff_lines_since_backup = get_diff_between_commits(
                        backup_start_commit, latest_commit_hash
                    )
                    lines_added_since_backup = sum(
                        1
                        for line in diff_lines_since_backup
                        if line.startswith("+") and not line.startswith("+++")
                    )
                    lines_removed_since_backup = sum(
                        1
                        for line in diff_lines_since_backup
                        if line.startswith("-") and not line.startswith("---")
                    )
                    incremental_lines = (
                        lines_added_since_backup + lines_removed_since_backup
                    )

                    if incremental_lines > 1000:
                        # Create a backup branch before compression
                        try:
                            # Generate backup branch name (format: backup/YYYY-MM-DD_HH-MM-SS)
                            backup_branch = (
                                f"backup/{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}"
                            )

                            # Create a backup branch pointing to latest_commit_hash
                            # Note: git branch only creates a branch and does not switch the current branch
                            subprocess.run(
                                ["git", "branch", backup_branch, latest_commit_hash],
                                capture_output=True,
                                check=True,
                            )
                            PrettyOutput.auto_print(
                                f"✅ Backup branch created: {backup_branch} (changes exceed 1000 lines, automatically backed up, please manually confirm the commit)"
                            )
                            # Update the last backup commit point; the next backup will start calculating from here
                            self.last_backup_commit = latest_commit_hash
                        except subprocess.CalledProcessError as e:
                            PrettyOutput.auto_print(f"⚠️ Failed to create backup branch: {str(e)}")
                        except Exception as e:
                            PrettyOutput.auto_print(f"⚠️ Backup branch creation exception: {str(e)}")
            else:
                reject_reason = get_last_commit_reject_reason()
                final_ret += "\nModification rejected\n"
                if reject_reason:
                    final_ret += f"# Rejection reason: {reject_reason}\n"
                final_ret += f"# Patch preview (by file):\n{per_file_preview}"
        else:
            return
        # User confirms the final result
        if commited:
            self._append_to_session_prompt(final_ret)
            return
        PrettyOutput.auto_print(final_ret, lang="markdown")  # Keep syntax highlighting
        if not is_confirm_before_apply_patch() or user_confirm(
            "Use this reply?", default=True
        ):
            self._append_to_session_prompt(final_ret)
            return
        # User did not confirm; allow entering a custom reply as an additional hint
        custom_reply = get_multiline_input("Please enter a custom reply")
        if custom_reply.strip():  # If the custom reply is empty, do not set an additional hint
            self.set_addon_prompt(custom_reply)
        self._append_to_session_prompt(final_ret)
        return

    def ask_llm_about_large_deletion(
        self, detection_result: Dict[str, int], preview: str
    ) -> bool:
        """Ask the large model whether the large code deletion is reasonable

        Parameters:
            detection_result: detection result dictionary, containing 'insertions', 'deletions', 'net_deletions'
            preview: patch preview content

        Returns:
            bool: returns True if the large model considers it reasonable, otherwise returns False
        """
        insertions = detection_result["insertions"]
        deletions = detection_result["deletions"]
        net_deletions = detection_result["net_deletions"]

        prompt = f"""Large code deletion detected; please judge whether it is reasonable:

Statistics:
- Added lines: {insertions}
- Deleted lines: {deletions}
- Net deleted lines: {net_deletions}

Patch preview:
{preview}

Please carefully analyze the above code changes and judge whether this large code deletion is reasonable. Possible cases include:
1. Refactoring code, removing redundant or outdated code
2. Simplifying the implementation, replacing a complex implementation with more concise code
3. Removing unused code or features
4. Accidentally deleting important code

Please answer using the following protocol (must contain exactly one of the following markers):
- If you consider these deletions reasonable, answer: <!!!YES!!!>
- If you consider these deletions unreasonable or risky, answer: <!!!NO!!!>

Please answer strictly in the protocol format and do not add other content.
"""

        # Ensure the model instance exists
        if self.model is None:
            raise ValueError("Model instance is empty, cannot perform the query")

        try:
            PrettyOutput.auto_print("🤖 Asking the large model to judge whether the large code deletion is reasonable...")
            # Directly use the current model instance, preserving the full conversation context
            response = self.model.chat_until_success(prompt)

            # Parse the answer using the defined protocol markers
            if "<!!!YES!!!>" in response:
                PrettyOutput.auto_print("✅ Large model confirmed: code deletion is reasonable")
                return True
            elif "<!!!NO!!!>" in response:
                PrettyOutput.auto_print("⚠️ Large model confirmed: code deletion is unreasonable")
                return False
            else:
                # If the protocol marker cannot be found, default to considering it unreasonable (conservative strategy)
                PrettyOutput.auto_print(
                    f"⚠️ Protocol marker not found, defaulting to unreasonable. Answer content: {response[:200]}"
                )
                return False
        except Exception as e:
            # If the query fails, default to considering it unreasonable (conservative strategy)
            PrettyOutput.auto_print(f"⚠️ Failed to query the large model: {str(e)}, defaulting to unreasonable")
            return False

    def _get_code_reviewer(self) -> CodeReviewer:
        """Get the CodeReviewer instance."""
        return CodeReviewer(
            model=self.model,
            start_commit=self.start_commit,
            non_interactive=self.non_interactive,
            quick_mode=self.quick_mode,
        )

    def _truncate_diff_for_review(self, git_diff: str, token_ratio: float = 0.4) -> str:
        """Truncate the git diff to fit within the token limit (delegated to CodeReviewer)."""
        return self._get_code_reviewer().truncate_diff_for_review(git_diff, token_ratio)

    def _generate_review_target(self, max_retries: int = 3) -> str:
        """Generate the goals and acceptance criteria for code review (delegated to CodeReviewer)."""
        return self._get_code_reviewer().generate_review_target(max_retries)

    def _build_review_prompts(
        self,
        review_target: str,
        git_diff: str,
        modification_history: Optional[str] = None,
        start_commit: Optional[str] = None,
    ) -> tuple:
        """Build the prompts for the review Agent (delegated to CodeReviewer)."""
        return self._get_code_reviewer().build_review_prompts(
            review_target=review_target,
            git_diff=git_diff,
            modification_history=modification_history,
            start_commit=start_commit,
        )

    def _check_and_get_git_diff(self) -> Optional[str]:
        """Check and obtain the git diff (delegated to CodeReviewer)."""
        return self._get_code_reviewer().check_and_get_git_diff()


@app.command()
def eli(
    llm_group: Optional[str] = typer.Option(
        None, "-g", "--llm-group", help="Model group to use, overrides the setting in the config file"
    ),
    tool_group: Optional[str] = typer.Option(
        None, "-G", "--tool-group", help="Tool group to use, overrides the setting in the config file"
    ),
    config_file: Optional[str] = typer.Option(
        None, "-f", "--config", help="Config file path"
    ),
    task: Optional[str] = typer.Option(None, "-T", "--task", help="Task description to process"),
    task_file: Optional[str] = typer.Option(
        None, "--task-file", help="Read the task description from a file"
    ),
    append_tools: Optional[str] = typer.Option(
        None, "--append-tools", help="List of tools to append, separated by commas"
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
    prefix: str = typer.Option(
        "",
        "--prefix",
        help="Commit message prefix (separated by spaces)",
    ),
    suffix: str = typer.Option(
        "",
        "--suffix",
        help="Commit message suffix (separated by newlines)",
    ),
    non_interactive: bool = typer.Option(
        False,
        "-n",
        "--non-interactive",
        help="Enable non-interactive mode: users cannot interact with the command, and the script execution timeout is limited to 5 minutes",
    ),
    rule_names: Optional[str] = typer.Option(
        None,
        "--rule-names",
        help="Specify a list of rule names, separated by commas, to read the corresponding rule contents from the rules.yaml file",
    ),
    disable_review: bool = typer.Option(
        False,
        "--disable-review",
        help="Disable code review: do not perform automatic code review after code modification is completed",
    ),
    review_max_iterations: int = typer.Option(
        0,
        "--review-max-iterations",
        help="Maximum number of code review iterations; review stops when the limit is reached (default 0, meaning unlimited)",
    ),
    worktree: bool = typer.Option(
        False,
        "-w",
        "--worktree",
        help="Enable git worktree mode, developing on an independent branch",
    ),
    dispatch: bool = typer.Option(
        False,
        "-d",
        "--dispatch",
        help="Dispatch the task to a new tmux window for execution (only valid in a tmux environment); the current process exits",
    ),
    optimize_system_prompt: bool = typer.Option(
        False,
        "-o",
        "--optimize-system-prompt",
        help="Automatically optimize the system prompt: use the large model to optimize the system prompt based on user requirements",
    ),
    web_gateway: bool = typer.Option(
        False,
        "--web-gateway",
        help="Enable the Web Gateway service (WebSocket input/output)",
    ),
    quick_mode: bool = typer.Option(
        False,
        "-q",
        "--quick",
        help="Turbo mode: cancel task classification, automatic rule loading, context recommendation, and methodology loading",
    ),
    quiet: bool = typer.Option(
        False,
        "-Q",
        "--quiet",
        help="Quiet mode: suppress console output (event/gateway output is still kept), used for reducing log noise in scenarios such as evaluation",
    ),
    print_prompt: bool = typer.Option(
        False,
        "--print-prompt",
        help="Print hint information (overrides the config file setting)",
    ),
    web_gateway_port: int = typer.Option(
        8000,
        "--web-gateway-port",
        help="Web Gateway listen port",
    ),
    proxy_node: Optional[str] = typer.Option(
        None,
        "--proxy-node",
        help="Target node ID to which HTTP proxy requests are forwarded",
    ),
    master_url: Optional[str] = typer.Option(
        None,
        "--master-url",
        help="Master node URL, used for forwarding HTTP proxy requests",
    ),
    agent_id: Optional[str] = typer.Option(
        None,
        "--agent-id",
        help="Agent ID, the unique identifier assigned by the Web Gateway's AgentManager",
    ),
) -> None:
    """HaijunBot main entry point."""
    # Handle task description: prefer reading from file
    if task and task_file:
        PrettyOutput.auto_print("❌ Error: cannot use --task and --task-file parameters at the same time")
        raise typer.Exit(code=1)

    # Status file path for tmux parallel tasks
    status_file_path = None
    web_gateway_server = None

    if task_file:
        try:
            import json
            from pathlib import Path

            with open(task_file, "r", encoding="utf-8") as file_handle:
                file_content = file_handle.read()

            # Try to parse as JSON to obtain the status_file field
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
                    # Not JSON format or no task_desc field, use the file content directly
                    task = file_content
            except json.JSONDecodeError:
                # Not JSON format, use the file content directly
                task = file_content

        except (Exception, FileNotFoundError) as e:
            PrettyOutput.auto_print(f"❌ Error: unable to read task description from file: {str(e)}")
            raise typer.Exit(code=1)

    # Non-interactive mode requires the task to be passed from the command line
    if non_interactive and not (task and str(task).strip()):
        PrettyOutput.auto_print(
            "❌ Non-interactive mode is enabled: task content must be passed with --task, because multi-line input is unavailable."
        )
        raise typer.Exit(code=2)

    # Handle the --dispatch parameter: dispatch the task to a new tmux window
    if dispatch:
        if not (task and str(task).strip()):
            PrettyOutput.auto_print(
                "❌ Error: the --dispatch parameter must be used together with the --task parameter"
            )
            raise typer.Exit(code=1)

        PrettyOutput.auto_print("ℹ️ Dispatching task to a new tmux window...")
        success = dispatch_to_tmux_window(task, sys.argv)
        if success:
            PrettyOutput.auto_print("✅ Task successfully dispatched to a new tmux window")
            raise typer.Exit(code=0)
        else:
            PrettyOutput.auto_print(
                "❌ Task dispatch failed: unable to create tmux window or pane, please check the tmux configuration"
            )
            raise typer.Exit(code=1)

    # Detect tmux and start it when needed (after argument parsing)
    # Pass config_file so the configuration is loaded before the check
    check_and_launch_tmux(config_file=config_file)

    init_env(
        "Welcome to HaijunBot-CodeAgent, your code engineering assistant is ready!",
        config_file=config_file,
        llm_group=llm_group,
    )

    # Set proxy node
    if proxy_node:
        jglobals.proxy_node = proxy_node
    if master_url:
        jglobals.master_url = master_url
    if agent_id:
        jglobals.agent_id = agent_id

    if web_gateway:
        try:
            import threading

            import uvicorn

            from haijunbot.haijunbot_web_gateway.app import create_app

            # Token authentication
            auth_token = os.environ.get("HAIJUNBOT_AUTH_TOKEN")
            if auth_token:
                pass  # validate_gateway_token() reads directly from environment variables

            # Create a custom FastAPI app, add the status query endpoint
            from fastapi import FastAPI, Request
            from fastapi.responses import JSONResponse
            from haijunbot.haijunbot_web_gateway.app import get_current_execution_status

            custom_app = FastAPI()

            @custom_app.get("/status")
            async def get_status() -> dict:
                """Get the Agent running status.

                Return status description:
                - execution_status: task execution status (running/waiting_multi/waiting_single)
                - status: process status (always returns running, because the process is still running)
                - non_interactive: whether in non-interactive mode
                """
                from haijunbot.haijunbot_utils.globals import get_current_agent

                agent = get_current_agent()
                return {
                    "execution_status": get_current_execution_status(),
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
                """Get the diff from start_commit to the current code (structured data).

                Return:
                    dict: a dict containing structured diff data
                        - diff: raw diff text (compatible with the legacy interface)
                        - files: list of structured data
                """
                from haijunbot.haijunbot_utils.globals import (
                    global_agents,
                    running_agent_stack,
                )
                from haijunbot.haijunbot_code_agent.diff_visualizer import (
                    parse_diff_to_structured_data,
                )

                # Get the root agent (the first in running_agent_stack, i.e. the earliest started agent)
                if running_agent_stack:
                    root_agent_name = running_agent_stack[0]
                    root_agent = global_agents.get(root_agent_name)
                    if (
                        root_agent
                        and hasattr(root_agent, "start_commit")
                        and root_agent.start_commit
                    ):
                        diff_content = get_diff_between_commits(root_agent.start_commit)
                        # Parse into structured data
                        structured_data = parse_diff_to_structured_data(diff_content)
                        return {"diff": diff_content, "files": structured_data}
                    # When there is no start_commit, if the working directory is a git repository, return the diff of uncommitted changes in the working tree
                    if root_agent and hasattr(root_agent, "root_dir"):
                        work_dir = root_agent.root_dir
                    else:
                        work_dir = os.getcwd()
                    try:
                        is_git_repo = subprocess.run(
                            ["git", "rev-parse", "--is-inside-work-tree"],
                            cwd=work_dir,
                            capture_output=True,
                            text=False,
                        )
                        if (
                            is_git_repo.returncode == 0
                            and is_git_repo.stdout.strip() == b"true"
                        ):
                            diff_result = subprocess.run(
                                ["git", "diff"],
                                cwd=work_dir,
                                capture_output=True,
                                text=False,
                            )
                            if diff_result.returncode == 0:
                                diff_content = diff_result.stdout.decode(
                                    "utf-8", errors="replace"
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

            @custom_app.post("/sessions/save")
            async def save_session():
                """Save the current session and return the file path."""
                try:
                    from haijunbot.haijunbot_utils.globals import (
                        global_agents,
                        running_agent_stack,
                    )

                    # Get the root agent (the first in running_agent_stack, i.e. the earliest started agent)
                    if not running_agent_stack:
                        return {"success": False, "error": "No active agent"}

                    root_agent_name = running_agent_stack[0]
                    agent = global_agents.get(root_agent_name)

                    if agent is None:
                        return {"success": False, "error": "No active agent"}

                    # Call the session_manager's save_session method
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

                When the Token changes after the main gateway restarts, the sub-gateway notifies the Agent to update the Token through this endpoint.

                Parameters:
                    token: the new authentication Token

                Return:
                    dict: operation result
                """
                try:
                    # Skip verification when synchronizing the Token after a gateway restart (X-Internal-Sync marker, limited to 127.0.0.1 local requests)
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

                Parameters:
                    sender_id: sender ID
                    content: message content

                Return:
                    dict: operation result
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

                    # If the Agent is waiting for input, inject directly into the input stream for instant delivery
                    if jglobals.input_inject_callback is not None:
                        jglobals.input_inject_callback(message)
                        delivered = "instant"
                    else:
                        # Otherwise store in the buffer and wait for the next loop iteration to consume
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

            os.environ["IS_AGENT_PROCESS"] = "1"
            config = uvicorn.Config(
                create_app(custom_app=custom_app),
                host="127.0.0.1",
                port=web_gateway_port,
                log_level="info",
            )
            web_gateway_server = uvicorn.Server(config)
            thread = threading.Thread(target=web_gateway_server.run, daemon=True)
            thread.start()
            PrettyOutput.auto_print(
                f"🌐 Web Gateway started: ws://127.0.0.1:{web_gateway_port}/ws"
            )
        except Exception as web_gateway_err:
            try:
                from haijunbot.haijunbot_gateway.manager import set_current_gateway

                set_current_gateway(None)
            except Exception as e:
                save_exception(e, module="haijunbot_code_agent.code_agent", function="eli")
                pass
            PrettyOutput.auto_print(f"⚠️ Failed to start Web Gateway: {str(web_gateway_err)}")

    # CodeAgent single-instance mutex: changed to repository-dimension locking (deferred until after locating the repository root)
    # Lock acquisition is moved to after confirming and switching to the git root directory

    # Sync CLI options to the global configuration after initializing the environment, to avoid being overwritten by init_env
    try:
        if llm_group:
            set_config("llm_group", str(llm_group))
        if tool_group:
            set_config("tool_group", str(tool_group))
        if restore or restore_session is not None or is_auto_resume_session():
            set_config("restore_session", True)
            # If the user specified a file path, check whether the file exists
            if restore_session is not None and restore_session != "":
                if not os.path.exists(restore_session):
                    PrettyOutput.auto_print(f"❌ Session file does not exist: {restore_session}")
                    return
        if print_prompt:
            set_config("print_prompt", True)
        if quiet:
            set_config("quiet", True)
    except Exception:
        # Silently ignore synchronization exceptions, without affecting the main flow
        pass

    try:
        subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        curr_dir_path = os.getcwd()
        PrettyOutput.auto_print(f"⚠️ Warning: the current directory '{curr_dir_path}' is not a git repository.")
        init_git = (
            True
            if non_interactive
            else user_confirm(
                f"Do you want to initialize a new git repository in '{curr_dir_path}'?", default=True
            )
        )
        if init_git:
            try:
                subprocess.run(
                    ["git", "init"],
                    check=True,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                )
                PrettyOutput.auto_print("✅ Successfully initialized the git repository.")

                # Initialize the .gitignore file, containing default ignore rules for all languages
                from haijunbot.haijunbot_utils.git_utils import (
                    get_default_gitignore_templates,
                )

                gitignore_path = ".gitignore"
                default_templates = get_default_gitignore_templates()
                with open(gitignore_path, "w", encoding="utf-8", newline="\n") as f:
                    f.write(default_templates + "\n")
                PrettyOutput.auto_print("✅ Created .gitignore and added default ignore rules for each language")
            except (subprocess.CalledProcessError, FileNotFoundError) as e:
                PrettyOutput.auto_print(f"❌ Failed to initialize git repository: {e}")
                sys.exit(1)
        else:
            PrettyOutput.auto_print("ℹ️ Operation canceled. HaijunBot needs to run in a git repository.")
            sys.exit(0)

    curr_dir = os.getcwd()
    find_git_root_and_cd(curr_dir)
    # Get the git repository root directory (for file locks and worktree management)
    repo_root = os.getcwd()
    # After locating the git root directory, lock by repository dimension, to avoid cross-repository mutex
    # In worktree mode no file lock needs to be created, because worktree itself is meant to isolate different tasks
    if not worktree:
        try:
            lock_name = f"code_agent_{hashlib.md5(repo_root.encode('utf-8'), usedforsecurity=False).hexdigest()}.lock"
            _acquire_single_instance_lock(lock_name=lock_name)
        except Exception:
            # Fall back to the global lock, ensuring at least mutex protection
            _acquire_single_instance_lock(lock_name="code_agent.lock")

    # Worktree management
    worktree_manager = None
    original_branch = None
    if worktree:
        try:
            PrettyOutput.auto_print("🌿 Git Worktree mode is enabled")
            worktree_manager = WorktreeManager(repo_root)
            original_branch = worktree_manager.get_current_branch()
            PrettyOutput.auto_print(f"📍 Current branch: {original_branch}")

            # Create worktree
            worktree_path = worktree_manager.create_worktree()

            # Switch to the worktree directory
            os.chdir(worktree_path)
            repo_root = worktree_path
            PrettyOutput.auto_print(f"✅ Switched to worktree directory: {worktree_path}")
        except Exception as e:
            PrettyOutput.auto_print(f"❌ Failed to create worktree: {str(e)}")
            sys.exit(1)
    try:
        output_content: Optional[str] = ""
        import json

        try:
            exit_code = 0
            error_message = ""
            try:
                if task:
                    # Single-task mode: create an agent and execute
                    agent = CodeAgent(
                        need_summary=False,
                        append_tools=append_tools,
                        tool_group=tool_group,
                        non_interactive=non_interactive,
                        rule_names=rule_names,
                        disable_review=disable_review,
                        review_max_iterations=review_max_iterations,
                        allow_savesession=True,
                        optimize_system_prompt=optimize_system_prompt,
                        quick_mode=quick_mode or is_enable_quick_mode(),
                    )

                    # Try to restore the session
                    if restore or restore_session is not None:
                        if agent.restore_session(
                            restore_session if restore_session else True
                        ):
                            # Display the actual restored session file name
                            restored_file = agent.session.last_restored_session
                            if restored_file:
                                file_basename = os.path.basename(restored_file)
                                PrettyOutput.auto_print(
                                    f"✅ Session restored from {file_basename}."
                                )
                        else:
                            PrettyOutput.auto_print("⚠️ Unable to restore session.")

                    output_content = cast(CodeAgent, agent).run(
                        task, prefix=prefix, suffix=suffix
                    )
                    # Single-task mode: exit directly after the task completes
                    raise typer.Exit(code=0)
                else:
                    # Loop task mode: create a new agent instance for each iteration, to avoid cross-task contamination

                    # Create the first agent instance (for session restoration and the first task)
                    agent = CodeAgent(
                        need_summary=False,
                        append_tools=append_tools,
                        tool_group=tool_group,
                        non_interactive=non_interactive,
                        rule_names=rule_names,
                        disable_review=disable_review,
                        review_max_iterations=review_max_iterations,
                        allow_savesession=True,
                        optimize_system_prompt=optimize_system_prompt,
                        quick_mode=quick_mode or is_enable_quick_mode(),
                    )

                    # Detect historical sessions consistent with the current commit (only in interactive mode and when restore_session is not specified)
                    if (
                        not non_interactive
                        and not restore
                        and not restore_session
                        and not is_auto_resume_session()
                    ):
                        try:
                            current_commit = get_latest_commit_hash()
                            if current_commit:
                                matching_sessions = (
                                    agent.session._find_sessions_by_commit(
                                        current_commit
                                    )
                                )
                                if matching_sessions:
                                    selected_session = agent.session._prompt_to_restore_matching_sessions(
                                        matching_sessions
                                    )
                                    if selected_session:
                                        # The user chooses to restore the session, use the unified restore method
                                        # This method performs complete detection: commit consistency, platform re-creation, token compatibility
                                        session_name = agent.session._read_session_name(
                                            selected_session
                                        )
                                        if agent.session.restore_session_from_file(
                                            selected_session, session_name
                                        ):
                                            # Set the first flag to False, to avoid the run() method performing requirement classification and methodology loading
                                            agent.first = False
                                            file_basename = os.path.basename(
                                                selected_session
                                            )
                                            PrettyOutput.auto_print(
                                                f"✅ Session restored from {file_basename}."
                                            )
                        except Exception as e:
                            # A detection failure does not affect the main flow
                            PrettyOutput.auto_print(f"⚠️  Failed to detect historical session: {e}")

                    # If session restoration is specified, restore the session first (let the user choose the session first, then enter the requirement)
                    if (
                        restore
                        or restore_session is not None
                        or is_auto_resume_session()
                    ):
                        if agent.restore_session(
                            restore_session if restore_session else True
                        ):
                            # Display the actual restored session file name
                            restored_file = agent.session.last_restored_session
                            if restored_file:
                                file_basename = os.path.basename(restored_file)
                                PrettyOutput.auto_print(
                                    f"✅ Session restored from {file_basename}."
                                )
                        else:
                            PrettyOutput.auto_print("⚠️ Unable to restore session.")

                    user_input = get_multiline_input("Please enter your requirement (Ctrl+C to exit)")
                    if not user_input:
                        raise typer.Exit(code=0)

                    # Use the current agent to execute the task
                    output_content = cast(CodeAgent, agent).run(
                        user_input, prefix=prefix, suffix=suffix
                    )

                    # Task exits normally
                    raise typer.Exit(code=0)
            except typer.Exit:
                # Normal exit, set the success status
                exit_code = 0
                error_message = ""
                # When agent.run() ends normally, output_content should already have a value
            except Exception as exec_err:
                exit_code = 1
                error_message = str(exec_err)
                raise
        finally:
            # If it is a tmux parallel task, write the status file
            if status_file_path:
                import json
                from pathlib import Path

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
                    def _convert_to_string(content: Any) -> str:
                        if content is None:
                            return ""
                        try:
                            # Try to serialize, if it fails then convert to a string
                            json.dumps(content)
                            return json.dumps(content, ensure_ascii=False, indent=2)
                        except (TypeError, ValueError):
                            # When serialization is not possible, convert to a string
                            return str(content)

                    output_content_str = _convert_to_string(output_content)
                    try:
                        output_file.write_text(output_content_str, encoding="utf-8")
                    except Exception as output_err:
                        # If writing the output fails, log the error
                        PrettyOutput.auto_print(
                            f"⚠️ Failed to write output file: {str(output_err)}"
                        )
                        pass

                    # Write the error file
                    if exit_code != 0 and error_message:
                        error_file = status_file_path.with_suffix(".error")
                        try:
                            error_file.write_text(error_message, encoding="utf-8")
                        except Exception as e:
                            save_exception(
                                e,
                                module="haijunbot_code_agent.code_agent",
                                function="_convert_to_string",
                            )
                            pass
                except Exception as status_err:
                    PrettyOutput.auto_print(f"⚠️ Failed to write status file: {str(status_err)}")

            # Worktree merge logic (ensure all exit paths execute it)
            if worktree and worktree_manager and original_branch:
                _handle_worktree_merge(
                    worktree_manager, original_branch, non_interactive
                )

            if web_gateway_server is not None:
                try:
                    web_gateway_server.should_exit = True
                except Exception as e:
                    save_exception(
                        e,
                        module="haijunbot_code_agent.code_agent",
                        function="_convert_to_string",
                    )
                    pass
                try:
                    from haijunbot.haijunbot_gateway.manager import set_current_gateway

                    set_current_gateway(None)
                except Exception as e:
                    save_exception(
                        e,
                        module="haijunbot_code_agent.code_agent",
                        function="_convert_to_string",
                    )
                    pass

    except typer.Exit:
        raise
    except RuntimeError as e:
        PrettyOutput.auto_print(f"❌ Error: {str(e)}")
        sys.exit(1)


def _handle_worktree_merge(
    worktree_manager: "WorktreeManager",
    original_branch: str,
    non_interactive: bool,
) -> None:
    """Handle the worktree rebase and merge logic

    Uses the rebase strategy: first rebase the worktree branch onto the original branch,
    then merge via fast-forward, keeping a linear history.

    Parameters:
        worktree_manager: WorktreeManager instance
        original_branch: original branch name
        non_interactive: whether in non-interactive mode
    """
    try:
        worktree_info = worktree_manager.get_worktree_info()
        worktree_branch = worktree_info.get("worktree_branch")
        worktree_path = worktree_info.get("worktree_path")

        PrettyOutput.auto_print(f"🌿 Worktree branch: {worktree_branch}")
        PrettyOutput.auto_print(f"📁 Worktree path: {worktree_path}")

        # Ask the user whether to rebase and merge (interactive mode) or execute automatically (non-interactive mode)
        should_merge = False
        if non_interactive:
            should_merge = True
            PrettyOutput.auto_print("🤖 Non-interactive mode: automatically rebase and merge the worktree branch")
        else:
            should_merge = user_confirm(
                f"Rebase and merge the worktree branch '{worktree_branch}' back into '{original_branch}'?",
                default=True,
            )

        if should_merge:
            # Rebase and merge the worktree branch
            merge_success = worktree_manager.merge_back(
                original_branch, non_interactive
            )
            if merge_success:
                PrettyOutput.auto_print("✅ Worktree branch successfully rebased and merged")
                # Automatically clean up the worktree directory
                PrettyOutput.auto_print("🧹 Cleaning up worktree directory...")
                cleanup_success = worktree_manager.cleanup()
                if cleanup_success:
                    PrettyOutput.auto_print(
                        f"✅ Worktree directory automatically deleted: {worktree_path}"
                    )
                else:
                    PrettyOutput.auto_print(
                        f"⚠️ Failed to delete worktree directory, please clean up manually: {worktree_path}"
                    )
                    PrettyOutput.auto_print(f"   git worktree remove {worktree_branch}")
            else:
                PrettyOutput.auto_print(
                    f"⚠️ Rebase/merge failed or canceled, worktree branch '{worktree_branch}' retained"
                )
                PrettyOutput.auto_print(
                    "💡 Tip: you can manually rebase and merge or clean up the worktree later:"
                )
                PrettyOutput.auto_print(f"   cd {worktree_path}")
                PrettyOutput.auto_print(f"   git checkout {original_branch}")
                PrettyOutput.auto_print(f"   git rebase {worktree_branch}")
        else:
            PrettyOutput.auto_print(
                f"ℹ️ worktree branch '{worktree_branch}' retained, you can manually rebase and merge later"
            )
            PrettyOutput.auto_print(f"💡 Tip: worktree path: {worktree_path}")

    except Exception as e:
        PrettyOutput.auto_print(f"❌ Error while handling worktree merge: {str(e)}")


def main() -> None:
    """Application entry point."""
    app()


if __name__ == "__main__":
    main()
