# -*- coding: utf-8 -*-
# Standard library imports
import datetime
import json
import os
import platform
import re
from enum import Enum
from pathlib import Path
from typing import Any
from typing import Callable
from typing import cast
from typing import Dict
from typing import List
from typing import Optional
from typing import Tuple
from typing import Union

# Third-party library imports
from haijunbot.haijunbot_agent.builtin_input_handler import builtin_input_handler
from haijunbot.haijunbot_agent.callback_loader import CallbackLoader
from haijunbot.haijunbot_agent.model_switcher import ModelSwitcher
from haijunbot.haijunbot_agent.event_bus import EventBus
from haijunbot.haijunbot_agent.events import AFTER_ADDON_PROMPT
from haijunbot.haijunbot_agent.events import AFTER_HISTORY_CLEAR
from haijunbot.haijunbot_agent.events import AFTER_MODEL_CALL
from haijunbot.haijunbot_agent.events import AFTER_SUMMARY
from haijunbot.haijunbot_agent.events import BEFORE_ADDON_PROMPT
from haijunbot.haijunbot_agent.events import BEFORE_HISTORY_CLEAR
from haijunbot.haijunbot_agent.events import BEFORE_MODEL_CALL
from haijunbot.haijunbot_agent.events import BEFORE_SUMMARY
from haijunbot.haijunbot_agent.events import BEFORE_TOOL_FILTER
from haijunbot.haijunbot_agent.events import INTERRUPT_TRIGGERED
from haijunbot.haijunbot_agent.events import TASK_COMPLETED
from haijunbot.haijunbot_agent.events import TASK_STARTED
from haijunbot.haijunbot_agent.events import TOOL_FILTERED
from haijunbot.haijunbot_agent.file_context_handler import file_context_handler
from haijunbot.haijunbot_agent.memory_manager import MemoryManager
from haijunbot.haijunbot_agent.rules_manager import RulesManager

# Local library imports
# haijunbot_agent related
from haijunbot.haijunbot_utils.config import is_enable_quick_mode
from haijunbot.haijunbot_utils.decision import decide_choice
from haijunbot.haijunbot_utils.exception_utils import save_exception
from haijunbot.haijunbot_utils.config import is_enable_request_classification
from haijunbot.haijunbot_agent.prompt_builder import build_action_prompt
from haijunbot.haijunbot_agent.prompt_builder import get_tool_registry
from haijunbot.haijunbot_agent.prompt_manager import PromptManager
from haijunbot.haijunbot_agent.history_compressor import HistoryCompressor
from haijunbot.haijunbot_agent.prompts import DEFAULT_SUMMARY_PROMPT

# Keep re-exporting for the public API (history summary/compression moved to history_compressor.py)
from haijunbot.haijunbot_agent.prompts import SUMMARY_REQUEST_PROMPT as SUMMARY_REQUEST_PROMPT
from haijunbot.haijunbot_agent.protocols import OutputHandlerProtocol
from haijunbot.haijunbot_agent.run_loop import AgentRunLoop, ensure_str
from haijunbot.haijunbot_agent.session_manager import SessionManager
from haijunbot.haijunbot_agent.task_analyzer import TaskAnalyzer
from haijunbot.haijunbot_agent.task_list import TaskListManager
from haijunbot.haijunbot_agent.tool_executor import execute_tool_call
from haijunbot.haijunbot_agent.user_interaction import UserInteractionHandler
from haijunbot.haijunbot_agent.utils import join_prompts
from haijunbot.haijunbot_memory_organizer.memory_organizer import MemoryOrganizer

# haijunbot_platform related
from haijunbot.haijunbot_platform.base import BasePlatform
from haijunbot.haijunbot_platform.registry import PlatformRegistry
from haijunbot.haijunbot_tools.registry import ToolRegistry

# haijunbot_utils related
from haijunbot.haijunbot_utils.config import get_addon_prompt_threshold
from haijunbot.haijunbot_utils.config import get_data_dir
from haijunbot.haijunbot_utils.config import get_normal_platform_name
from haijunbot.haijunbot_utils.config import get_tool_filter_threshold
from haijunbot.haijunbot_utils.config import is_enable_memory_organizer
from haijunbot.haijunbot_utils.config import is_execute_tool_confirm
from haijunbot.haijunbot_utils.config import is_force_save_memory
from haijunbot.haijunbot_utils.config import is_use_analysis
from haijunbot.haijunbot_utils.globals import clear_current_agent
from haijunbot.haijunbot_utils.globals import get_interrupt
from haijunbot.haijunbot_utils.globals import get_short_term_memories
from haijunbot.haijunbot_utils.globals import make_agent_name
from haijunbot.haijunbot_utils.globals import set_interrupt
from haijunbot.haijunbot_utils.globals import set_current_agent
from haijunbot.haijunbot_platform.content_types import ContentBlock
from haijunbot.haijunbot_utils.input import get_multiline_input
from haijunbot.haijunbot_utils.input import user_confirm
from haijunbot.haijunbot_utils.output import PrettyOutput
from haijunbot.haijunbot_utils.tag import ot

__all__ = [
    "Agent",
    "LoopAction",
    "show_agent_startup_stats",
    "get_multiline_input",
    "user_confirm",
]


class SafeEncoder(json.JSONEncoder):
    """Custom JSON encoder for handling non-serializable objects

    Mainly used for serialization during session save, handling:
    - Function objects: converted to their string representation
    - Other non-serializable objects: attempted to convert to a string
    """

    def default(self, o: Any) -> Any:
        """Handle non-serializable objects

        Args:
            o: the object to serialize

        Returns:
            a serializable object
        """
        # Handle function objects
        if callable(o):
            # Try to get the function name
            if hasattr(o, "__name__"):
                return f"<function:{o.__name__}>"
            # Try to get the class name (for callable objects)
            elif hasattr(o, "__class__"):
                return f"<callable:{o.__class__.__name__}>"
            else:
                return "<function>"

        # For other non-serializable objects, try converting to a string
        try:
            return str(o)
        except Exception:
            return "<unserializable_object>"


def show_agent_startup_stats(
    agent_name: str,
    model_name: str,
    tool_registry_instance: Optional[Any] = None,
    platform_name: Optional[str] = None,
) -> None:
    """Print statistics at startup

    Args:
        agent_name: the name of the Agent
        model_name: the model name being used
    """
    try:
        # Get the tool count
        # Create a temporary tool registry class to fetch all tools (without applying filters)
        class TempToolRegistry(ToolRegistry):
            def _apply_tool_config_filter(self) -> None:
                """Override the filter method to do nothing"""
                pass

        # Get the count of all tools
        tool_registry_all = TempToolRegistry()
        total_tool_count = len(tool_registry_all.tools)

        # Get the count of available tools (after filtering)
        if tool_registry_instance is not None:
            available_tool_count = len(tool_registry_instance.get_all_tools())
        else:
            tool_registry = ToolRegistry()
            available_tool_count = len(tool_registry.get_all_tools())

        global_memory_dir = Path(get_data_dir()) / "memory" / "global_long_term"
        global_memory_count = 0
        if global_memory_dir.exists():
            global_memory_count = len(list(global_memory_dir.glob("*.json")))

        # Check project memory
        project_memory_dir = Path(".haijunbot/memory")
        project_memory_count = 0
        if project_memory_dir.exists():
            project_memory_count = len(list(project_memory_dir.glob("*.json")))

        # Check short-term memory
        short_term_memories = get_short_term_memories()
        short_term_memory_count = len(short_term_memories) if short_term_memories else 0

        # Get the current working directory
        current_dir = os.getcwd()

        # Build the welcome message
        platform = platform_name or get_normal_platform_name()
        welcome_message = (
            f"{agent_name} initialized - using the {platform} platform with the {model_name} model"
        )

        stats_parts = [
            f"🛠️  Tools: [bold green]{available_tool_count}/{total_tool_count}[/bold green] (available/total)",
            f"🧠  Global memory: [bold yellow]{global_memory_count}[/bold yellow]",
        ]

        # If there is project memory, add it to the stats
        if project_memory_count > 0:
            stats_parts.append(
                f"📝  Project memory: [bold magenta]{project_memory_count}[/bold magenta]"
            )

        # If there is short-term memory, add it to the stats
        if short_term_memory_count > 0:
            stats_parts.append(
                f"💭  Short-term memory: [bold blue]{short_term_memory_count}[/bold blue]"
            )

        PrettyOutput.print_resource_overview_panel(
            welcome_message=welcome_message,
            current_dir=current_dir,
            stats_parts=stats_parts,
        )

    except Exception as e:
        PrettyOutput.auto_print(f"⚠️ Failed to load statistics: {e}")


origin_agent_system_prompt = f"""
<role>
# 🤖 HaijunBot Agent
You are a professional task execution assistant that creates and executes detailed plans based on user needs.
</role>

## Core Mode

### ARCHER Workflow Description

#### ANALYZE (Analysis)
Understand the user's needs, clarify the task goals and constraints, and identify the rules that may be required. If the requirements are unclear, proactively ask clarifying questions. **Analyze only, do not design solutions**.

#### RULE (Load Rules)
Use `load_rule` to load relevant rules and best practices, and understand the rule constraints and requirements. Execute only when professional guidance is needed.

#### COLLECT (Gather Information)
Read-only gathering of necessary information: when needed, use the `memory` tool (action=retrieve) to retrieve relevant memories for historical context; use suitable tools (such as search tools, query tools, etc.) to precisely locate and obtain relevant information, never speculate. For code tasks, use search tools (rg, fd) to locate files (always filter by directory/suffix), and read the target files and their direct dependencies.

#### HYPOTHESIZE (Design Solutions)
Propose multiple feasible solutions based on the gathered information, compare their pros, cons, risks and costs, and ask the user for preferences. After the user responds, decide whether to create a task list with `task_list_manager` based on task complexity, and make a detailed execution plan. **Acceptance criteria and clear execution steps must be specified for every solution**, ensuring they are quantifiable, verifiable and executable.

**Note: after this phase completes, you must wait for user confirmation before entering the EXECUTE phase.**

**After the user confirms the plan, you must use the `memory` tool (action=save) to store the confirmed plan in short-term memory** for reference during execution. The saved content should include:
- The complete execution plan (all steps)
- Scope of impact (files modified/added/deleted)
- Risk assessment and mitigation strategies
- Acceptance criteria
- Task understanding and tech stack information

Suggested tags such as: ["Execution Plan", "Task Plan", "Current Task"], for later retrieval.

**The HYPOTHESIZE phase must output the following structured content:**

1. **Task Understanding**
   - Clearly describe your understanding of the user's needs
   - Identify the core goals and constraints of the task
   - Clarify the tech stack and dependency relationships that may be involved

2. **Execution Plan**
   - List the detailed execution steps (numbered in order)
   - Each step should include: operations, files/tools involved, expected results
   - For complex tasks, state whether `task_list_manager` will be used to split the task

3. **Scope of Impact**
   - List the files to be modified (added/modified/deleted)
   - Clarify the functional modules that may be affected
   - Assess dependencies on other code

4. **Risk Assessment**
   - Identify potential risk points and difficulties
   - Clarify mitigation strategies and fallback options
   - Assess task complexity (simple/medium/complex)

5. **Acceptance Criteria**
   - Clarify the acceptance criteria for each solution
   - Clarify how to verify task completion
   - List the required tests and verification steps

**Output format example:**
```
## Task Understanding
[Your understanding of the task and its core goals]

## Execution Plan
1. [Step 1: operations, files involved, expected results]
2. [Step 2: operations, files involved, expected results]
...

## Scope of Impact
- Modified files: [file list]
- Added files: [file list]
- Modules involved: [module list]

## Risk Assessment
- Risk points: [risk description]
- Mitigation strategies: [strategy description]
- Task complexity: [simple/medium/complex]

## Acceptance Criteria
- [Criterion 1]
- [Criterion 2]
...

Please confirm this plan is correct; after confirmation I will start executing (enter "confirm", "continue" or "ENTER EXECUTE").
```

#### EXECUTE (Execution)
Execute precisely according to the plan: read before writing (use read_code to locate → edit_file/edit_file_by_line to modify, write_file for large rewrites), make the smallest changes, one tool call per response, and verify after every change.

#### REVIEW (Retrospective)
Comprehensively review the work results: check code quality (syntax/function/style), verify that the functionality is complete, confirm that all affected code has been considered, ensure supporting changes are made (such as docs, tests, config, etc.), assess the impact scope and potential risks, clean up temporary files, and confirm it can be safely reverted.

### ARCHER Flexible Execution Guide
- **Preparation phase (A→R→C) flexible**: ANALYZE is required; RULE and COLLECT can be executed or reordered as needed; simple tasks may skip RULE/COLLECT
- **Execution phase (H→E→R) strict order**: HYPOTHESIZE → EXECUTE → REVIEW must be executed in order, no skipping
- **Each phase can be reverted**: any phase can revert to the previous phase as needed, forming an iterative loop

## Execution Rules
1. **Single operation**: each response contains only one tool call
2. **No fabrication**: must be based on actual results, never assume
3. **Task list**: use task_list_manager for complex tasks, execute simple tasks directly
4. **Must verify**: code needs to compile and pass functional verification
5. **Mode switch**: requires the explicit signal "ENTER [MODE]"

## Tool Usage
- Prefer task_list_manager for complex tasks
- execute_task must provide the additional_info parameter
- Do not call multiple tools at the same time

<system_info>
OS: {platform.platform()} {platform.version()}
Time: {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
</system_info>
"""


class LoopAction(Enum):
    SKIP_TURN = "skip_turn"
    CONTINUE = "continue"
    COMPLETE = "complete"


class Agent:
    # Attribute type annotations to satisfy static type checkers
    event_bus: EventBus
    memory_manager: MemoryManager
    task_analyzer: TaskAnalyzer
    prompt_manager: PromptManager
    model: BasePlatform
    session: SessionManager

    # Commit-related attributes (used by CodeAgent)
    prefix: str
    suffix: str

    # CodeAgent-specific attributes (only present on CodeAgent instances)
    disable_review: bool
    review_max_iterations: int
    tool_group: Optional[str]
    root_dir: str
    start_commit: Optional[str]
    last_backup_commit: Optional[str]

    # Whether the tmux layout has been set (class-level flag)
    _tmux_layout_set: bool = False

    def agent_type(self) -> str:
        """Get the agent type"""
        return self._agent_type

    def clear_history(self) -> None:
        """
        Clears the current conversation history by delegating to the session manager.
        Critical flows call the functions directly; the event bus is only used for non-critical flows (e.g. logging, monitoring).
        """
        # Get the current session file path for the hint
        from haijunbot.haijunbot_utils.dialogue_recorder import get_global_recorder

        recorder = get_global_recorder()
        session_file_path = recorder.get_session_file_path()

        # Critical path: call memory_manager directly to ensure the memory prompt
        try:
            self.memory_manager._ensure_memory_prompt(agent=self)
        except Exception as e:
            save_exception(e, module="haijunbot_agent.__init__", function="clear_history")
            pass

        # Non-critical path: broadcast the before-clear-history event (for logging, monitoring, etc.)
        try:
            self.event_bus.emit(BEFORE_HISTORY_CLEAR, agent=self)
        except Exception as e:
            save_exception(e, module="haijunbot_agent.__init__", function="clear_history")
            pass

        # Clear the session history and reset the model state
        self.session.clear_history()
        # Reset the addon_prompt skip-rounds counter
        self._addon_prompt_skip_rounds = 0
        # Reset the no-tool-call counter
        self._no_tool_call_count = 0
        # Reset the last LLM response content
        self._last_response_content = ""

        # Tell the user where the session file is
        if Path(session_file_path).exists():
            PrettyOutput.auto_print(f"💾 The current session record has been saved to: {session_file_path}")
            PrettyOutput.auto_print("🤖 The model can read this file to understand the full conversation history")

        # Reset the system prompt afterwards to ensure the system constraints still take effect
        try:
            self._setup_system_prompt()
        except Exception as e:
            save_exception(e, module="haijunbot_agent.__init__", function="clear_history")
            pass

        # Non-critical path: broadcast the after-clear-history event (for logging, monitoring, etc.)
        try:
            self.event_bus.emit(AFTER_HISTORY_CLEAR, agent=self)
        except Exception as e:
            save_exception(e, module="haijunbot_agent.__init__", function="clear_history")
            pass

    def __del__(self) -> None:
        # Only stop recording when recording was started
        # Fallback: if run() did not complete (exception/not called), still notify the daemon to exit gracefully,
        # so it does not mistake normal process destruction for an unexpected kill and write to disk.
        try:
            self._notify_session_daemon_quit()
        except Exception:
            pass

    def get_user_origin_input(self) -> Union[str, List[ContentBlock]]:
        """Get the original user input

        Returns:
            Union[str, List[ContentBlock]]: the original user input (without any enhancement processing)
        """
        return self.original_user_input

    def add_multimodal_content(self, content: List[ContentBlock]) -> None:
        """Add multimodal content to the current conversation context

        Args:
            content: list of multimodal content
        """
        if not content:
            return

        # Check whether multimodal is supported
        if hasattr(self, "model") and not self.model.supports_multimodal():
            warning_msg = "⚠️ The current model does not support multimodal input, skipped adding multimodal content. To use multimodal features, set supports_multimodal: true in llm_config"
            PrettyOutput.auto_print(warning_msg)
            return

        # Get the current prompt
        current_prompt = self.session.prompt

        # If the current prompt is a string, convert it to a list
        if isinstance(current_prompt, str):
            if current_prompt.strip():
                new_prompt: List[ContentBlock] = [
                    {"type": "text", "text": current_prompt}
                ]
            else:
                new_prompt = []
        else:
            new_prompt = current_prompt.copy() if current_prompt else []

        # Add the new content
        new_prompt.extend(content)

        # Update session.prompt
        self.session.prompt = new_prompt

        # Log it
        PrettyOutput.auto_print(f"✅ Added {len(content)} multimodal content blocks to the conversation context")

    def get_tool_usage_prompt(self) -> str:
        """Get the tool usage prompt"""
        # Extract task context text for coarse tool filtering by relevance when there are many tools
        task_context: Optional[str] = None
        if isinstance(self.original_user_input, str):
            task_context = self.original_user_input
        elif isinstance(self.original_user_input, list):
            texts = [
                block.get("text", "")
                for block in self.original_user_input
                if isinstance(block, dict) and block.get("text")
            ]
            task_context = " ".join(texts) if texts else None
        return build_action_prompt(self.output_handler, task_context)

    def __new__(cls, *args: Any, **kwargs: Any) -> "Agent":
        if kwargs.get("agent_type") == "code_agent":
            try:
                from haijunbot.haijunbot_code_agent.code_agent import CodeAgent
            except ImportError as e:
                raise RuntimeError(
                    "CodeAgent could not be imported. Please ensure haijunbot_code_agent is installed correctly."
                ) from e

            # Remove agent_type to avoid an infinite loop, and pass through all other args
            kwargs.pop("agent_type", None)
            return CodeAgent(**kwargs)
        else:
            return super().__new__(cls)

    def __init__(
        self,
        system_prompt: Optional[str] = None,
        name: str = "HaijunBot",
        description: str = "",
        summary_prompt: Optional[str] = None,
        auto_complete: bool = True,
        output_handler: Optional[List[OutputHandlerProtocol]] = None,
        use_tools: Optional[List[str]] = None,
        execute_tool_confirm: Optional[bool] = None,
        need_summary: bool = True,
        multiline_inputer: Optional[Callable[[str], str]] = None,
        use_methodology: Optional[bool] = None,
        use_analysis: Optional[bool] = None,
        force_save_memory: Optional[bool] = None,
        files: Optional[List[str]] = None,
        confirm_callback: Optional[Callable[[str, bool], bool]] = None,
        non_interactive: Optional[bool] = True,
        in_multi_agent: Optional[bool] = None,
        allow_savesession: bool = False,
        rule_names: Optional[str] = None,
        optimize_system_prompt: bool = False,
        enable_auto_rule_select: bool = True,
        model_type: str = "normal",
        quick_mode: bool = False,
        **kwargs: Any,
    ):
        """Initialize a HaijunBot Agent instance

        Args:
            system_prompt: system prompt defining the Agent's behavior guidelines
            name: Agent name, defaults to "HaijunBot"
            description: Agent description

            summary_prompt: task summary prompt template
            auto_complete: whether to complete the task automatically
            execute_tool_confirm: whether to confirm before executing a tool
            need_summary: whether a summary should be generated
            multiline_inputer: multiline input handler
            use_methodology: whether to use the methodology
            use_analysis: whether to use task analysis
            force_save_memory: whether to force saving memory
            confirm_callback: user confirmation callback, signature (tip: str, default: bool) -> bool; defaults to the CLI's user_confirm
            non_interactive: whether to run in non-interactive mode (highest priority, overrides env vars and config)
            allow_savesession: whether SaveSession commands are allowed (default False; only the hjb/hca main programs pass True)
            rule_names: comma-separated rule name list for loading the specified rules
            optimize_system_prompt: if True, use user input to optimize the system prompt on the first run()
            enable_auto_rule_select: whether to enable automatic rule selection (default True)
            model_type: model type, one of "normal", "smart", "cheap" (default "normal")
        """

        # Initialize the base attributes
        self._init_base_attributes(
            name,
            description,
            system_prompt,
            auto_complete,
            need_summary,
            use_methodology,
            use_analysis,
            execute_tool_confirm,
            summary_prompt,
            force_save_memory,
            files,
            use_tools,
            non_interactive,
            in_multi_agent,
            allow_savesession,
        )

        # Model type configuration
        self._model_type = model_type
        # Manual model switch flag (disables automatic switching)
        self._manual_model_switch = False
        # Quick mode configuration (combining CLI args and config options)
        self.quick_mode = quick_mode or is_enable_quick_mode()

        # Initialize the core components
        self._init_model()
        self._init_session()
        self._init_handlers(multiline_inputer, output_handler, use_tools or [])

        # User interaction initialization (must run after _init_handlers since it needs self.multiline_inputer)
        self._init_user_interaction(confirm_callback, non_interactive)

        # Config parsing and setting
        self._init_config(
            use_methodology,
            use_analysis,
            execute_tool_confirm,
            force_save_memory,
            summary_prompt,
        )

        # Initialize the event bus and managers
        self._init_managers()
        # Save the auto rule selection flag
        self._enable_auto_rule_select = enable_auto_rule_select
        # Load the rule content (ensures loaded_rules and loaded_rule_names are initialized)
        self.loaded_rules, self.loaded_rule_names = self.rules_manager.load_all_rules(
            rule_names
        )

        # Set up tools and system prompt
        self._setup_tools_and_prompt()

        # Set the deferred optimization flag (will optimize on the first run())
        self._optimize_system_prompt_on_first_run = optimize_system_prompt
        self._system_prompt_optimized = False

        # Dynamic callback loading
        self._load_after_tool_callbacks()
        self._load_all_event_callbacks()

        # Session real-time save daemon (only enabled for the main Agent; writes the latest snapshot when unexpectedly killed)
        self._session_daemon = None
        self._session_daemon_quit_sent = False
        self._start_session_daemon()

    def _start_session_daemon(self) -> None:
        """Start the session real-time save daemon subprocess (main Agent only).

        Enabled only when ``allow_savesession=True`` (the hjb/hca main programs); sub-Agents
        are not enabled. Platforms without ``os.fork`` (e.g. Windows) automatically fall back to not enabling it.
        """
        if not self.allow_savesession:
            return
        try:
            from haijunbot.haijunbot_agent.session_daemon import SessionDaemon

            daemon = SessionDaemon()
            if daemon.start():
                self._session_daemon = daemon
                # Record the PID of the process that created the daemon: only that process may notify it to exit,
                # preventing a subprocess (if later created via fork/multiprocessing) from wrongly sending quit
                self._session_daemon_owner_pid = os.getpid()
        except Exception as e:
            save_exception(
                e, module="haijunbot_agent.__init__", function="_start_session_daemon"
            )
            self._session_daemon = None

    def _send_session_snapshot(self) -> None:
        """Build the current session snapshot and send it to the daemon subprocess (in-memory, no disk write).

        Triggered by ``_fire_after_tool_call`` after each tool call, keeping the daemon's
        in-memory snapshot close to the latest state at all times.
        """
        daemon = getattr(self, "_session_daemon", None)
        if daemon is None or not daemon.enabled:
            return
        # Only the process that created the daemon may send snapshots; subprocesses never send
        owner_pid = getattr(self, "_session_daemon_owner_pid", None)
        if owner_pid is not None and os.getpid() != owner_pid:
            return
        try:
            from haijunbot.haijunbot_agent.session_daemon import build_snapshot_files

            snapshot = self.session.build_session_snapshot()
            if not snapshot:
                return
            session_file, files = snapshot
            daemon.send_snapshot(build_snapshot_files(session_file, files))
        except Exception as e:
            save_exception(
                e, module="haijunbot_agent.__init__", function="_send_session_snapshot"
            )

    def _notify_session_daemon_quit(self) -> None:
        """Notify the daemon subprocess of a "graceful exit" (idempotent, no disk write).

        The graceful exit path is already persisted by save_session; the daemon only needs to clean up its memory and exit.
        """
        if getattr(self, "_session_daemon_quit_sent", False):
            return
        self._session_daemon_quit_sent = True
        daemon = getattr(self, "_session_daemon", None)
        if daemon is None:
            return
        # Only the process that created the daemon may notify it to exit; subprocesses never send
        owner_pid = getattr(self, "_session_daemon_owner_pid", None)
        if owner_pid is not None and os.getpid() != owner_pid:
            return
        try:
            daemon.send_quit()
        except Exception as e:
            save_exception(
                e,
                module="haijunbot_agent.__init__",
                function="_notify_session_daemon_quit",
            )

    def _init_base_attributes(
        self,
        name: str,
        description: str,
        system_prompt: Optional[str],
        auto_complete: bool,
        need_summary: bool,
        use_methodology: Optional[bool],
        use_analysis: Optional[bool],
        execute_tool_confirm: Optional[bool],
        summary_prompt: Optional[str],
        force_save_memory: Optional[bool],
        files: Optional[List[str]],
        use_tools: Optional[List[str]],
        non_interactive: Optional[bool],
        in_multi_agent: Optional[bool],
        allow_savesession: bool,
    ) -> None:
        """Initialize the base attributes

        Args:
            name: Agent name
            description: Agent description
            system_prompt: system prompt
            auto_complete: whether to complete automatically
            need_summary: whether a summary is needed
            use_methodology: whether to use the methodology
            use_analysis: whether to use analysis
            execute_tool_confirm: whether to confirm before executing a tool
            summary_prompt: summary prompt
            force_save_memory: whether to force saving memory
            llm_group: model group
            files: file list
            use_tools: tools to use
            non_interactive: whether non-interactive mode
            in_multi_agent: whether in multi-agent mode
            allow_savesession: whether session saving is allowed
        """
        # Identity and description
        self.name = make_agent_name(name)
        self.description = description
        self.system_prompt = system_prompt or ""

        # Behavior control flags (original argument values; parsed/overridden later based on config)
        self.auto_complete = bool(auto_complete)
        self.need_summary = bool(need_summary)
        self.use_methodology = use_methodology
        self.use_analysis = use_analysis
        self.execute_tool_confirm = execute_tool_confirm
        self.summary_prompt = summary_prompt
        self.force_save_memory = force_save_memory

        # Resources and environment configuration
        self.files = files or []
        self.use_tools = use_tools
        self.non_interactive = non_interactive

        # Multi-agent run flag: controls auto-complete behavior in non-interactive mode
        self.in_multi_agent = bool(in_multi_agent)

        # Runtime state variables
        self.first = True
        self.run_input_handlers_next_turn = False
        self.user_data: Dict[str, Any] = {}
        self.pin_content: str = ""  # Stores the pinned content
        self.original_user_input: Union[str, List[ContentBlock]] = (
            ""  # Records the original user input
        )
        self.recent_memories: List[str] = []  # The most recent 10 memory entries
        self.MAX_RECENT_MEMORIES = 10  # Maximum number of memories
        self.return_control_on_auto_complete = False  # Return control to the user after auto-complete

        # Permission and state control
        self.allow_savesession = bool(allow_savesession)  # SaveSession command permission control
        self._addon_prompt_skip_rounds = 0  # Tracks consecutive rounds without an addon_prompt

        # Memory tag collection: records all memory tags produced by this agent and its sub-agents
        self.memory_tags: set = set()  # use set for automatic deduplication
        self._no_tool_call_count = (
            0  # Tracks consecutive turns with no tool calls (used for the tool usage hint in non-interactive mode)
        )
        self._last_response_content = (
            ""  # Records the most recent LLM response content (for manual fixes, etc.)
        )
        self._last_handler_returned = False  # Records whether the last input handler returned a message
        self._agent_type = "agent"
        self._last_responses: List[str] = []  # Records recent LLM responses (for duplicate detection)
        self._repeat_detected = False  # Whether a duplicate response has been detected
        self._repeat_count = 0  # Count of consecutive identical responses
        self._repeat_escalation_level = 0  # Duplicate response escalation level (0/1/2)

        # Native tool call state (plan A: loop expansion in the run_loop main loop; each round goes through compression/injection)
        self._pending_native_tool_calls: Optional[List[Dict[str, Any]]] = (
            None  # Pending native tool_calls to execute
        )
        self._native_continue: bool = (
            False  # Whether in native-tool continuation state (previous round already filled back tool results)
        )

        # Background pre-compression related attributes
        self._pre_compressed_summary: Optional[str] = None  # The summary generated by background pre-compression
        self._pre_compressing: bool = False  # Whether background pre-compression is running
        self._pre_compress_snapshot_count: int = 0  # Number of messages in the snapshot at pre-compression time
        # Force-continue-after-full-compression flag: compression empties session.prompt; if the model does not call a tool
        # next round, the main loop uses this to skip _get_next_user_action so control is not returned to the user
        self._force_continue_after_compress: bool = False

    def add_memory_tags(self, tags: List[str]) -> None:
        """Add memory tags to the memory_tags set

        Args:
            tags: list of tags to add
        """
        if tags:
            self.memory_tags.update(tags)

    def get_memory_tags(self) -> List[str]:
        """Get all memory tags

        Returns:
            the tag list (sorted)
        """
        return sorted(list(self.memory_tags))

    def _init_user_interaction(
        self,
        confirm_callback: Optional[Callable[[str, bool], bool]],
        non_interactive: Optional[bool],
    ) -> None:
        """Initialize the user interaction components

        Args:
            confirm_callback: user confirmation callback
            non_interactive: whether non-interactive mode
        """
        # User confirmation callback: defaults to the CLI's user_confirm; can be injected externally to support TUI/GUI
        self.confirm_callback: Callable[[str, bool], bool] = (
            confirm_callback or user_confirm
        )

        # Initialize the user interaction wrapper, keeping backward compatibility
        # Note: self.multiline_inputer is already set in _init_handlers
        self.user_interaction = UserInteractionHandler(
            self.multiline_inputer, self.confirm_callback
        )
        # Point the confirm function at the wrapped confirm, keeping existing calls unchanged
        self.confirm_callback = self.user_interaction.confirm

        # Non-interactive mode parameter support: allows explicit control via constructor args, convenient when other Agents call it
        # Only an Agent instance attribute; not written to env vars or global config to avoid cross-Agent pollution
        try:
            # Prefer the constructor arg; default to False if not provided
            self.non_interactive = (
                bool(non_interactive) if non_interactive is not None else False
            )
        except Exception:
            # Defensive fallback
            self.non_interactive = False

    def _init_config(
        self,
        use_methodology: Optional[bool],
        use_analysis: Optional[bool],
        execute_tool_confirm: Optional[bool],
        force_save_memory: Optional[bool],
        summary_prompt: Optional[str],
    ) -> None:
        """Parse and set the configuration items

        Args:
            use_methodology: whether to use the methodology
            use_analysis: whether to use analysis
            execute_tool_confirm: whether to confirm before executing a tool
            force_save_memory: whether to force saving memory
            summary_prompt: summary prompt
        """
        # Parse the use_methodology config (methodology system removed; param kept as a compatibility placeholder)
        try:
            resolved_use_methodology = bool(
                use_methodology if use_methodology is not None else True
            )
        except Exception:
            resolved_use_methodology = (
                bool(use_methodology) if use_methodology is not None else True
            )

        # Parse the use_analysis config
        try:
            resolved_use_analysis = bool(
                use_analysis if use_analysis is not None else is_use_analysis()
            )
        except Exception:
            resolved_use_analysis = (
                bool(use_analysis) if use_analysis is not None else True
            )

        # Parse the execute_tool_confirm config
        try:
            resolved_execute_tool_confirm = bool(
                execute_tool_confirm
                if execute_tool_confirm is not None
                else is_execute_tool_confirm()
            )
        except Exception:
            resolved_execute_tool_confirm = (
                bool(execute_tool_confirm)
                if execute_tool_confirm is not None
                else False
            )

        # Parse the force_save_memory config
        try:
            resolved_force_save_memory = bool(
                force_save_memory
                if force_save_memory is not None
                else is_force_save_memory()
            )
        except Exception:
            resolved_force_save_memory = (
                bool(force_save_memory) if force_save_memory is not None else False
            )

        # Apply the parsed config values
        self.use_methodology = resolved_use_methodology
        self.use_analysis = resolved_use_analysis
        self.execute_tool_confirm = resolved_execute_tool_confirm
        self.summary_prompt = summary_prompt or DEFAULT_SUMMARY_PROMPT
        self.force_save_memory = resolved_force_save_memory

        # Set auto_complete based on the run mode
        # In multi-agent mode, do not auto-complete by default (even in non-interactive); only enable when auto_complete=True is explicitly passed
        if self.in_multi_agent:
            self.auto_complete = bool(self.auto_complete)
        else:
            # In non-interactive mode, auto-complete by default; otherwise keep the passed auto_complete value
            self.auto_complete = bool(
                self.auto_complete or (self.non_interactive or False)
            )

    def _init_managers(self) -> None:
        """Initialize the event bus and managers"""
        # Initialize the event bus (must precede the managers so they can safely subscribe during construction)
        self.event_bus = EventBus()

        # Hook/Modifier mechanism (independent of EventBus)
        # Hook: interception type; a callback returning False blocks execution
        self._before_tool_call_hooks: List[Callable] = []
        # Modifier: modification type; callback returns the modified value
        self._before_model_call_modifiers: List[Callable] = []
        self._before_summary_modifiers: List[Callable] = []

        # Initialize the feature managers
        self.memory_manager = MemoryManager(self)  # memory manager: manages long-term and short-term memory
        self.task_analyzer = TaskAnalyzer(self)  # task analyzer: analyzes task completion and satisfaction
        self.prompt_manager = PromptManager(self)  # prompt manager: builds and manages the system prompt
        self._history_compressor = HistoryCompressor(self)  # history summary/compression handler
        self._callback_loader = CallbackLoader(self)  # callback/event loading handler
        self._model_switcher = ModelSwitcher(self)  # model/platform switching handler

        # Initialize the task list manager (uses the current working directory as root_dir, or the subclass's root_dir if already set)
        root_dir = getattr(self, "root_dir", None) or os.getcwd()
        self.task_list_manager = TaskListManager(root_dir)

        # Initialize the rules manager (do not overwrite if a subclass already created it)
        if not hasattr(self, "rules_manager"):
            self.rules_manager = RulesManager(root_dir)

    def _setup_tools_and_prompt(self) -> None:
        """Set up tools and the system prompt"""
        # If force-save memory is configured, ensure the memory tool is available
        if self.force_save_memory:
            self._ensure_save_memory_tool()

        # Set the system prompt (built from the config and tool list)
        self._setup_system_prompt()

    def _init_model(self) -> None:
        """Initialize the model platform, selecting the platform by model_type (normal/smart/cheap)"""

        registry = PlatformRegistry()
        model_type = getattr(self, "_model_type", "normal")
        if model_type == "smart":
            self.model = registry.get_smart_platform()
        elif model_type == "cheap":
            self.model = registry.get_cheap_platform()
        else:
            self.model = registry.get_normal_platform()

        self.model.set_suppress_output(False)

        # Set the Agent reference so the Platform can call Agent methods (e.g. automatic summarization)
        self.model.agent = self

    def _init_session(self) -> None:
        """Initialize the session manager"""
        self.session = SessionManager(
            model=self.model, agent_name=self.name, agent=self
        )

    def _init_handlers(
        self,
        multiline_inputer: Optional[Callable[[str], str]],
        output_handler: Optional[List[OutputHandlerProtocol]],
        use_tools: List[str],
    ) -> None:
        """Initialize the various handlers"""
        default_handlers: List[Any] = [ToolRegistry()]
        handlers = output_handler or default_handlers
        self.output_handler = handlers
        self.set_use_tools(use_tools)
        self.input_handler = [
            builtin_input_handler,
            file_context_handler,
        ]
        self.multiline_inputer = multiline_inputer or get_multiline_input

    # ------------------------------------------------------------------
    # Model/platform switching: delegated to ModelSwitcher (implementation in model_switcher.py)
    # Keep the same-named methods so the public interface (including run_loop / code_agent back-calls) is unchanged.
    # ------------------------------------------------------------------
    def _switch_model_by_difficulty(self, difficulty: str) -> None:
        """Switch the model based on task difficulty (delegated to ModelSwitcher)"""
        return self._model_switcher.switch_model_by_difficulty(difficulty)

    def _classify_and_switch_model(
        self,
        user_input: Union[str, List[ContentBlock]],
        classify_fn: Callable,
        get_prompt_fn: Callable,
    ) -> None:
        """Perform request classification, model switching, sampling temperature adaptation and system prompt updates (delegated to ModelSwitcher)"""
        return self._model_switcher.classify_and_switch_model(
            user_input=user_input,
            classify_fn=classify_fn,
            get_prompt_fn=get_prompt_fn,
        )

    def _apply_task_temperature(self, temperature: Optional[float]) -> None:
        """Apply the recommended sampling temperature to the current model based on the task nature (delegated to ModelSwitcher)"""
        return self._model_switcher.apply_task_temperature(temperature)

    def _setup_system_prompt(self) -> None:
        """Set the system prompt"""
        """Set the system prompt"""
        prompt_text = self.prompt_manager.build_system_prompt(self)
        self.model.set_system_prompt(prompt_text)

    def optimize_system_prompt(self, user_requirement: str) -> None:
        """Optimize the system prompt based on user requirements

        Args:
            user_requirement: user requirement description, used to optimize the system prompt
        """
        try:
            from haijunbot.haijunbot_agent.prompt_optimizer import optimize_system_prompt

            # Get the current system prompt
            current_prompt = self.system_prompt

            # Optimize the system prompt
            optimized_prompt = optimize_system_prompt(
                current_system_prompt=current_prompt, user_requirement=user_requirement
            )

            # Update the system prompt
            if optimized_prompt and optimized_prompt != current_prompt:
                self.system_prompt = optimized_prompt
                # Reset the system prompt on the model
                self._setup_system_prompt()
        except Exception as e:
            PrettyOutput.auto_print(
                f"⚠️ System prompt optimization failed: {str(e)}, continuing with the original system prompt"
            )

    def set_user_data(self, key: str, value: Any) -> None:
        """Sets user data in the session."""
        self.session.set_user_data(key, value)

    def get_user_data(self, key: str) -> Optional[Any]:
        """Gets user data from the session."""
        return self.session.get_user_data(key)

    def get_remaining_token_count(self) -> int:
        """Get the remaining available token count

        Returns:
            int: the remaining available token count, or 0 if it cannot be fetched
        """
        if not self.model:
            return 0
        try:
            return self.model.get_remaining_token_count()
        except Exception:
            return 0

    def set_use_tools(self, use_tools: List[str]) -> None:
        """Set the list of tools to use"""
        for handler in self.output_handler:
            if isinstance(handler, ToolRegistry):
                if use_tools:
                    handler.use_tools(use_tools)
                break

    def set_addon_prompt(self, addon_prompt: str) -> None:
        """Sets the addon prompt in the session."""
        self.session.set_addon_prompt(addon_prompt)

    def set_run_input_handlers_next_turn(self, value: bool) -> None:
        """Sets the flag to run input handlers on the next turn."""
        self.run_input_handlers_next_turn = value

    def _multiline_input(self, tip: str, print_on_empty: bool) -> str:
        """
        Safe wrapper for multiline input to optionally suppress empty-input notice.
        If the configured multiline_inputer supports 'print_on_empty' keyword, pass it;
        otherwise, fall back to calling with a single argument for compatibility.
        """
        # Prefer going through the user interaction wrapper, so the UI can be replaced later
        try:
            return self.user_interaction.multiline_input(tip, print_on_empty)
        except Exception as e:
            save_exception(
                e, module="haijunbot_agent.__init__", function="_multiline_input"
            )
            pass
        try:
            # Try to pass the keyword for enhanced input handler
            return self.multiline_inputer(
                tip,
            )
        except TypeError:
            # Fallback for custom handlers that only accept one argument
            return self.multiline_inputer(tip)

    # ------------------------------------------------------------------
    # Callback/event loading: delegated to CallbackLoader (implementation in callback_loader.py)
    # Keep the same-named methods so the public interface is unchanged.
    # ------------------------------------------------------------------
    def _load_after_tool_callbacks(self) -> None:
        """Scan after_tool_call_cb_dirs and register callbacks (delegated to CallbackLoader)"""
        return self._callback_loader.load_after_tool_callbacks()

    def _load_event_callbacks(
        self,
        event_name: str,
        config_getter: Callable[[], List[str]],
        callback_names: List[str],
        target: str = "event_bus",
    ) -> None:
        """Generic callback loading method (delegated to CallbackLoader)"""
        return self._callback_loader.load_event_callbacks(
            event_name=event_name,
            config_getter=config_getter,
            callback_names=callback_names,
            target=target,
        )

    def _load_all_event_callbacks(self) -> None:
        """Load all event callbacks (delegated to CallbackLoader)"""
        return self._callback_loader.load_all_event_callbacks()

    def save_session(self) -> bool:
        """Saves the current session state by delegating to the session manager."""
        return self.session.save_session()

    def restore_session(
        self, restore_session: Optional[Union[bool, str]] = None
    ) -> bool:
        """Restores the session state by delegating to the session manager.

        Args:
            restore_session: the restore-session parameter.
                - True: interactively select a session file
                - str: specify a session file path
                - None/False: do not restore
        """
        if not restore_session:
            return False

        if isinstance(restore_session, str):
            # Restore from the specified file path
            session_restored = self.session.restore_session_from_file(restore_session)
        else:
            # Interactively select and restore
            session_restored = self.session.restore_session()

        if session_restored:
            self.first = False
        return session_restored

    def get_tool_registry(self) -> Optional[Any]:
        """Get the tool registry instance"""
        return get_tool_registry(self.output_handler)

    def _native_active(self) -> bool:
        """Whether the current agent should use native function calling."""
        try:
            from haijunbot.haijunbot_utils.config import is_enable_native_tool_calls

            if not is_enable_native_tool_calls():
                return False
            model = getattr(self, "model", None)
            if model is None:
                return False
            if not getattr(model, "supports_native_tool_calls", lambda: False)():
                return False
            if getattr(model, "_native_disabled", False):
                return False
            registry = self.get_tool_registry()
            if not registry or not getattr(registry, "tools", None):
                return False
            return True
        except Exception:
            return False

    def _native_tools(self) -> list:
        """Build the native tool schema required by the current platform."""
        from haijunbot.haijunbot_platform.haijun import HaijunModel
        from haijunbot.haijunbot_platform.native_tools import (
            build_juglow_tools,
            build_openai_tools,
        )
        from haijunbot.haijunbot_platform.openai import OpenAIModel

        registry = self.get_tool_registry()
        if not registry:
            return []
        if isinstance(self.model, OpenAIModel):
            return build_openai_tools(registry)
        if isinstance(self.model, HaijunModel):
            return build_juglow_tools(registry)
        return []

    def _execute_pending_native_calls(self) -> None:
        """Execute pending native tool_calls and fill back the role=tool results.

        Called by the run_loop main loop after each model call (plan A: native tool loop expanded into the main loop).
        After execution clears _pending_native_tool_calls and sets _native_continue for continuation next round.
        """
        calls = self._pending_native_tool_calls or []
        if not calls:
            return
        model = self.model
        outputs = self._execute_native_batch(calls)
        for call, out in zip(calls, outputs):
            call_id = call.get("id", "") or ""
            name = call.get("name", "") or "unknown"
            # Audit: record the native tool call (zero overhead when disabled)
            self._audit_log(
                "tool_call", tool_name=name, arguments=call.get("arguments") or {}
            )
            # Every tool_call_id must be answered back, or OpenAI/Juglow report pairing 400
            if call_id:
                model.append_native_tool_result(call_id, name, out)
        # Consistent with the text protocol: fire AFTER_TOOL_CALL callbacks and events after tool execution
        # (for side channels such as diff visualization / auto-commit / build validation / lint)
        self._fire_after_tool_call()
        self._pending_native_tool_calls = None
        self._native_continue = True

    def _run_native_until_content(self, message: str) -> str:
        """Run the native tool loop until the model returns pure content (for non-main-loop scenarios).

        Unlike the main-loop expansion approach, this method internally performs multiple rounds of
        tool_calls execution and fill-back, for callers such as memory_manager / task_analyzer that bypass run_loop.
        """
        from haijunbot.haijunbot_platform.haijun import HaijunModel
        from haijunbot.haijunbot_platform.openai import OpenAIModel
        from haijunbot.haijunbot_utils.globals import get_interrupt

        model = self.model
        if not isinstance(model, (OpenAIModel, HaijunModel)):
            return model.chat_until_success(message)

        content, calls = model.chat_native_once(
            message, self._native_tools(), append_user=True
        )
        guard = 0
        while calls and guard < 30:
            guard += 1
            self._pending_native_tool_calls = calls
            self._execute_pending_native_calls()
            if get_interrupt():
                break
            content, calls = model.chat_native_once(
                None, self._native_tools(), append_user=False
            )
        self._pending_native_tool_calls = None
        self._native_continue = False
        return content or ""

    def _fire_after_tool_call(self) -> None:
        """Fire AFTER_TOOL_CALL (delegated to CallbackLoader)"""
        # Session real-time save: refresh the daemon's in-memory snapshot after each tool call
        self._send_session_snapshot()
        return self._callback_loader.fire_after_tool_call()

    def _exec_native_one(self, call: Dict[str, Any]) -> str:
        """Execute a single native tool call serially (with confirmation gating and rejection handling)."""
        name = call.get("name", "")
        if not name:
            return ""
        if getattr(self, "execute_tool_confirm", False):
            try:
                ok = self.confirm_callback(f"Execute the native tool '{name}'?", False)
            except Exception:
                ok = False
            if not ok:
                return "The user refused to execute this tool; adjust the plan accordingly."
        try:
            registry = self.get_tool_registry()
            if registry is None:
                return f"Tool '{name}' execution failed: tool registry unavailable"
            return registry.execute_native_tool_call(
                name, call.get("arguments") or {}, self
            )
        except Exception as e:
            return f"Tool '{name}' execution failed with exception: {e}"

    def _execute_native_batch(self, calls: List[Dict[str, Any]]) -> List[str]:
        """Execute a batch of native tool_calls, returning each tool's result text in the original order.

        - If there are interactive/exclusive tools (execute_script/virtual_tty, etc.), user confirmation is needed, or there is only one call: execute serially one-by-one;
        - Otherwise execute mutually-independent read-only tools in parallel (thread pool, up to 4 concurrent).
        """
        non_parallel = {
            "execute_script",
            "virtual_tty",
            "task_list_manager",
            "gateway_manager",
            "edit_file",
            "edit_file_by_line",
            "write_file",
            "add_images",
            "meta_agent",
        }
        registry = self.get_tool_registry()

        def _is_serial(name: str) -> bool:
            # In the built-in list or the tool declaring interactive (user-defined tools can declare interactive=True)
            if name in non_parallel:
                return True
            if registry is None:
                return False
            tool = registry.get_tool(name)
            if tool is None:
                return False
            return bool(getattr(tool, "interactive", False))

        names = [c.get("name", "") for c in calls]
        any_serial = any(_is_serial(n) for n in names if n)
        parallel_ok = (
            not getattr(self, "execute_tool_confirm", False)
            and len(calls) > 1
            and bool(names)
            and not any_serial
        )
        if not parallel_ok:
            return [self._exec_native_one(c) for c in calls]

        from concurrent.futures import ThreadPoolExecutor

        def run(call: Dict[str, Any]) -> str:
            n = call.get("name", "")
            try:
                if registry is None:
                    return f"Tool '{n}' execution failed: tool registry unavailable"
                return registry.execute_native_tool_call(
                    n, call.get("arguments") or {}, self, record=False
                )
            except Exception as e:
                return f"Tool '{n}' execution failed with exception: {e}"

        with ThreadPoolExecutor(max_workers=min(len(calls), 4)) as executor:
            futures = [executor.submit(run, c) for c in calls]
            outputs = [f.result() for f in futures]

        # Record the executed tools uniformly under parallelism to avoid shared-state races
        try:
            prev = self.get_user_data("__executed_tools__")
            prev = prev if isinstance(prev, list) else []
            self.set_user_data("__executed_tools__", prev + [n for n in names if n])
            if names:
                self.set_user_data("__last_executed_tool__", names[-1])
        except Exception:
            pass
        return outputs

    def _ensure_save_memory_tool(self) -> None:
        """If force-save memory is configured, ensure the memory tool is in the use_tools list"""
        try:
            tool_registry = self.get_tool_registry()
            if not tool_registry:
                return

            # Check whether the memory tool is registered (tools are registered by default)
            if not tool_registry.get_tool("memory"):
                # If the tool itself does not exist, it cannot be used; return
                return

            # Check whether memory is in the use_tools list
            # If use_tools is None, it means all tools are used; no need to add
            if self.use_tools is None:
                return

            # If memory is not in the use_tools list, add it
            if "memory" not in self.use_tools:
                self.use_tools.append("memory")
                # Update the tool registry's tool list
                self.set_use_tools(self.use_tools)
        except Exception:
            # Ignore all errors; do not affect the main flow
            pass

    def get_event_bus(self) -> EventBus:
        """Get the event bus instance"""
        return self.event_bus

    def _call_model(
        self,
        message: Union[str, List[ContentBlock]],
        need_complete: bool = False,
        run_input_handlers: bool = True,
    ) -> str:
        """Call the AI model with retry logic

        Args:
            message: the message to send to the model, supporting plain text or multimodal content
            need_complete: whether a task completion marker is needed
            run_input_handlers: whether to run the input handlers

        Returns:
            str: the model's response

        Notes:
            1. Uses exponential backoff retry, up to 30 seconds
            2. Automatically processes the input handler chain
            3. Automatically appends the addon prompt
            4. Checks and handles the context length limit
        """
        # Process the input
        if run_input_handlers:
            message = self._process_input(message)
            if not message or self._last_handler_returned:
                return ""

        # Append the addon prompt
        message = self._add_addon_prompt(message, need_complete)

        # Broadcast the before-model-call event (does not affect the main flow)
        # Call the model (_invoke_model internally triggers the BEFORE_MODEL_CALL Modifier + Event)
        response = self._invoke_model(message)

        return response

    def _process_input(
        self, message: Union[str, List[ContentBlock]]
    ) -> Union[str, List[ContentBlock]]:
        """Process the input message

        Note: input handlers currently only support text messages. Multimodal messages skip the input handlers.
        """
        if isinstance(message, list):
            self._last_handler_returned = False
            return message

        for handler in self.input_handler:
            message, need_return = handler(message, self)
            if need_return:
                self._last_handler_returned = True
                return message
        self._last_handler_returned = False
        return message

    def _add_addon_prompt(
        self, message: Union[str, List[ContentBlock]], need_complete: bool
    ) -> Union[str, List[ContentBlock]]:
        """Append an addon prompt to the message

        Rules:
        1. If session.addon_prompt exists, use it first
        2. If the message length exceeds the threshold, add the default addon_prompt
        3. If no addon_prompt was added for 10 consecutive rounds, force adding one
        """
        # Broadcast the before-addon-prompt event (does not affect the main flow)
        try:
            self.event_bus.emit(
                BEFORE_ADDON_PROMPT,
                agent=self,
                need_complete=need_complete,
                current_message=message,
                has_session_addon=bool(self.session.addon_prompt),
            )
        except Exception as e:
            save_exception(
                e, module="haijunbot_agent.__init__", function="_add_addon_prompt"
            )
            pass

        addon_text = ""
        should_add = False

        if self.session.addon_prompt:
            # Prefer the addon_prompt set in the session
            addon_text = self.session.addon_prompt
            message = join_prompts([message, addon_text])
            self.session.addon_prompt = ""
            should_add = True
        else:
            threshold = get_addon_prompt_threshold()
            # Condition 1: the message length exceeds the threshold
            # For multimodal content, check the length of the text parts
            message_len = (
                len(message)
                if isinstance(message, str)
                else sum(
                    len(b.get("text", "")) if b.get("type") == "text" else 0
                    for b in message
                )
            )
            # Under native tool calls, do not auto-inject the default addon (tools come from the API tools, avoiding repeated instructions/interference with the native loop)
            if message_len > threshold and not self._native_active():
                addon_text = self.make_default_addon_prompt(need_complete)
                message = join_prompts([message, addon_text])
                should_add = True
            # Condition 2: if no addon_prompt was added for 10 consecutive rounds, force adding one (text protocol only)
            elif self._addon_prompt_skip_rounds >= 10 and not self._native_active():
                addon_text = self.make_default_addon_prompt(need_complete)
                message = join_prompts([message, addon_text])
                should_add = True

        # Update the counter: if an addon_prompt was added, reset the counter; otherwise increment
        # But skip counting if the input_handler already handled this round (e.g. executed a shell command)
        if should_add:
            self._addon_prompt_skip_rounds = 0
        elif not self._last_handler_returned:
            self._addon_prompt_skip_rounds += 1

        # Broadcast the after-addon-prompt event (does not affect the main flow)
        try:
            self.event_bus.emit(
                AFTER_ADDON_PROMPT,
                agent=self,
                need_complete=need_complete,
                addon_text=addon_text,
                final_message=message,
            )
        except Exception as e:
            save_exception(
                e, module="haijunbot_agent.__init__", function="_add_addon_prompt"
            )
            pass
        return message

    def _invoke_model(self, message: Union[str, List[ContentBlock]]) -> str:
        """Actually call the model to get a response"""
        if not self.model:
            raise RuntimeError("Model not initialized")

        # Modifier: call the before_model_call modifiers (modification type)
        # The callback returns the modified message, used to alter the prompt
        for modifier in self._before_model_call_modifiers:
            try:
                result = modifier(agent=self, message=message)
                if result is not None:
                    message = result
            except Exception as e:
                save_exception(
                    e, module="haijunbot_agent.__init__", function="_invoke_model"
                )
                pass

        # Event: before model call (notification type)
        try:
            self.event_bus.emit(
                BEFORE_MODEL_CALL,
                agent=self,
                message=message,
            )
        except Exception as e:
            save_exception(e, module="haijunbot_agent.__init__", function="_invoke_model")
            pass

        if self._native_active():
            # Native function calling: one model call per round; content is returned and tool_calls stored in
            # _pending_native_tool_calls; the run_loop main loop executes the tools, fills back role=tool, then continues
            # the next round, so every round goes through the main loop's context compression / input_buffer injection / round checks.
            from haijunbot.haijunbot_platform.haijun import HaijunModel
            from haijunbot.haijunbot_platform.openai import OpenAIModel

            model = self.model
            if not isinstance(model, (OpenAIModel, HaijunModel)):
                response = model.chat_until_success(message)
            else:
                if self._native_continue:
                    # Continuation round: the previous round's tool_calls were filled back as role=tool. If this round
                    # has supplementary messages (input_buffer injection / addon), append them as user messages so they take effect; otherwise continue based on history.
                    if isinstance(message, str) and message.strip():
                        content, calls = model.chat_native_once(
                            message, self._native_tools(), append_user=True
                        )
                    else:
                        content, calls = model.chat_native_once(
                            None, self._native_tools(), append_user=False
                        )
                    self._native_continue = False
                elif isinstance(message, str) and message.strip():
                    content, calls = model.chat_native_once(
                        message, self._native_tools(), append_user=True
                    )
                else:
                    content, calls = None, None
                self._pending_native_tool_calls = calls
                response = content or ""
        else:
            response = self.model.chat_until_success(message)
        # Defensive: the model may return an empty response (None or empty string); unify to an empty string and warn.
        # But empty content is normal when native tool calls return tool_calls (the model decided to call a tool rather than reply with text); do not warn.
        if not response and not self._pending_native_tool_calls:
            try:
                PrettyOutput.auto_print("⚠️ The model returned an empty response; fell back to an empty string.")
            except Exception as e:
                save_exception(
                    e, module="haijunbot_agent.__init__", function="_invoke_model"
                )
                pass
            response = ""

        # Event: after model call
        try:
            self.event_bus.emit(
                AFTER_MODEL_CALL,
                agent=self,
                message=message,
                response=response,
            )
        except Exception as e:
            save_exception(e, module="haijunbot_agent.__init__", function="_invoke_model")
            pass

        return response

    # ------------------------------------------------------------------
    # History summary/compression: delegated to HistoryCompressor (implementation in history_compressor.py)
    # Keep the same-named methods so the public interface (including run_loop / code_agent back-calls) is unchanged.
    # ------------------------------------------------------------------
    def _validate_summary(self, summary: str) -> tuple[bool, list[str]]:
        """Check whether the summary is acceptable (delegated to HistoryCompressor)"""
        return self._history_compressor.validate_summary(summary)

    def generate_summary(self, for_token_limit: bool = False) -> str:
        """Generate a summary of the conversation history (delegated to HistoryCompressor)"""
        return self._history_compressor.generate_summary(
            for_token_limit=for_token_limit
        )

    def _print_compression_summary(self, summary: str, compression_type: str) -> None:
        """Print the compression summary in a Panel (delegated to HistoryCompressor)"""
        return self._history_compressor.print_compression_summary(
            summary, compression_type
        )

    def _sliding_window_compression(self, window_size: Optional[int] = None) -> bool:
        """Sliding window compression (delegated to HistoryCompressor)"""
        return self._history_compressor.sliding_window_compression(
            window_size=window_size
        )

    def _start_background_pre_compression(self) -> None:
        """Start background pre-compression (delegated to HistoryCompressor)"""
        return self._history_compressor.start_background_pre_compression()

    def _check_and_use_pre_compressed_summary(self) -> bool:
        """Check and use the pre-compressed summary to rebuild the session (delegated to HistoryCompressor)"""
        return self._history_compressor.check_and_use_pre_compressed_summary()

    def _format_compressed_summary(self, compressed_summary: str) -> str:
        """Format the compressed summary (delegated to HistoryCompressor)"""
        return self._history_compressor.format_compressed_summary(compressed_summary)

    def _adaptive_compression(self) -> bool:
        """Adaptive compression (delegated to HistoryCompressor)"""
        return self._history_compressor.adaptive_compression()

    def _summarize_and_clear_history(
        self, trigger_reason: str = "Token limit triggered"
    ) -> str:
        """Summarize the current conversation and clear the history (delegated to HistoryCompressor)"""
        return self._history_compressor.summarize_and_clear_history(
            trigger_reason=trigger_reason
        )

    def _handle_history_with_summary(self) -> str:
        """Handle the history using the summary approach (delegated to HistoryCompressor)"""
        return self._history_compressor.handle_history_with_summary()

    def _format_summary_message(self, summary: str) -> str:
        """Format the summary message (delegated to HistoryCompressor)"""
        return self._history_compressor.format_summary_message(summary)

    def _get_task_list_info(self) -> str:
        """Get and format the current task list info

        Returns:
            str: formatted task list info, or an empty string if there is no task list
        """
        try:
            # Use the current Agent's task list manager to get all task list info
            if (
                not hasattr(self, "task_list_manager")
                or not self.task_list_manager.task_lists
            ):
                return ""

            all_task_lists_info = []

            # Iterate over all task lists
            for task_list_id, task_list in self.task_list_manager.task_lists.items():
                summary = self.task_list_manager.get_task_list_summary(task_list_id)
                if not summary:
                    continue

                # Build the task list summary info
                info_parts = []
                info_parts.append(f"📋 Task list: {summary['main_goal']}")
                info_parts.append(
                    f"   Total tasks: {summary['total_tasks']} | Pending: {summary['pending']} | Running: {summary['running']} | Completed: {summary['completed']}"
                )

                # If there are failed or abandoned tasks, also show them
                if summary["failed"] > 0 or summary["abandoned"] > 0:
                    status_parts = []
                    if summary["failed"] > 0:
                        status_parts.append(f"Failed: {summary['failed']}")
                    if summary["abandoned"] > 0:
                        status_parts.append(f"Abandoned: {summary['abandoned']}")
                    info_parts[-1] += f" | {' | '.join(status_parts)}"

                all_task_lists_info.append("\n".join(info_parts))

            if not all_task_lists_info:
                return ""

            return "\n\n".join(all_task_lists_info)

        except Exception:
            # Fail silently; do not interfere with the main flow
            return ""

    def _call_tools(self, response: str) -> Tuple[bool, Any]:
        """
        Delegates the tool execution to the external `execute_tool_call` function.
        """
        # Audit: record the text-protocol tool call (zero overhead when disabled; parses only when enabled)
        if self._is_audit_enabled():
            info = self._extract_tool_arguments(response)
            self._audit_log(
                "tool_call", tool_name=info["name"], arguments=info["arguments"]
            )
        return execute_tool_call(response, self)

    def _is_audit_enabled(self) -> bool:
        """Whether auditing is enabled (disabled by default; when disabled, no parsing is done, keeping zero overhead)."""
        try:
            from haijunbot.haijunbot_utils.config import is_enable_audit

            return bool(is_enable_audit())
        except Exception:
            return False

    def _extract_tool_arguments(self, response: str) -> Dict[str, Any]:
        """Extract the tool-call arguments dict from a text-protocol response, for audit redaction.

        Returns an empty dict when parsing fails or nothing is found; never raises an exception.
        Returns {"name": str, "arguments": dict}.
        """
        try:
            from haijunbot.haijunbot_utils.utils import extract_json_from_text
            from haijunbot.haijunbot_utils.jsonnet_compat import loads as json_loads

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
                args = tool_call.get("arguments")
                if isinstance(args, dict):
                    return {"name": tool_call.get("name", ""), "arguments": args}
            return {"name": "", "arguments": {}}
        except Exception:
            return {"name": "", "arguments": {}}

    def _audit_log(self, event_type: str, **data: Any) -> None:
        """Record one audit event (zero overhead when disabled; exceptions are silent and do not affect the main flow).

        The audit system is controlled by the enable_audit config option, disabled by default. When disabled, log_event
        returns immediately internally; the lazy import here avoids module-loading overhead.
        """
        try:
            from haijunbot.haijunbot_audit.audit import log_event

            log_event(event_type, **data)
        except Exception:
            pass

    def _complete_task(self, auto_completed: bool = False) -> str:
        """Complete the task and generate a summary (if needed)

        Returns:
            str: the task summary or completion status

        Notes:
            1. For the main Agent: may generate a methodology (if enabled)
            2. For sub-Agents: may generate a summary (if enabled)
            3. Uses a spinner to show the generation status
        """
        # Event-driven approach:
        # - TaskAnalyzer performs analysis and satisfaction collection by subscribing to before_summary/task_completed events
        # - MemoryManager saves memory by subscribing to before_history_clear/task_completed events (controlled by force_save_memory)
        # To reduce coupling, we no longer call the above components directly here; behavior is driven by events
        # Only check and organize memory when automatic memory organization is enabled
        if is_enable_memory_organizer():
            self._check_and_organize_memory()

        result = "Task completed"

        # 🔧 Fix: decouple task analysis from summarization; use_analysis is independent of need_summary
        # Critical path: call task_analyzer directly to run task analysis (it decides whether to ask based on the mode)
        if self.use_analysis:
            try:
                self.task_analyzer.trigger_task_analysis(auto_completed=auto_completed)
            except Exception as e:
                save_exception(
                    e, module="haijunbot_agent.__init__", function="_complete_task"
                )
                pass

        if self.need_summary:
            # Ensure the summary prompt is non-empty: fall back to the default prompt if None or blank
            safe_summary_prompt = self.summary_prompt or ""
            if (
                isinstance(safe_summary_prompt, str)
                and safe_summary_prompt.strip() == ""
            ):
                safe_summary_prompt = DEFAULT_SUMMARY_PROMPT
            # Note: do not write back to session.prompt, to avoid using an empty prompt after callbacks modify/clear it

            # Modifier: call the before_summary modifiers (modification type)
            # The callback returns the modified prompt, used to alter the summary prompt
            for modifier in self._before_summary_modifiers:
                try:
                    result = modifier(
                        agent=self,
                        prompt=safe_summary_prompt,
                        auto_completed=auto_completed,
                    )
                    if result is not None:
                        safe_summary_prompt = result
                except Exception as e:
                    save_exception(
                        e, module="haijunbot_agent.__init__", function="_complete_task"
                    )
                    pass

            # Non-critical path: broadcast the before-summary event (for logging, monitoring, etc.)
            try:
                self.event_bus.emit(
                    BEFORE_SUMMARY,
                    agent=self,
                    prompt=safe_summary_prompt,
                    auto_completed=auto_completed,
                    need_summary=self.need_summary,
                )
            except Exception as e:
                save_exception(
                    e, module="haijunbot_agent.__init__", function="_complete_task"
                )
                pass

            if not self.model:
                raise RuntimeError("Model not initialized")
            # Use the local variable directly to avoid being affected by event callbacks
            ret = self.model.chat_until_success(safe_summary_prompt)
            # Defensive: the model may return an empty response during summarization (None or empty string); unify to an empty string and warn
            if not ret:
                try:
                    PrettyOutput.auto_print(
                        "⚠️ The model returned an empty response during summarization; fell back to an empty string."
                    )
                except Exception as e:
                    save_exception(
                        e, module="haijunbot_agent.__init__", function="_complete_task"
                    )
                    pass
                ret = ""
            result = ret

            # Print the task summary content for the user to review
            if ret and ret.strip():
                try:
                    import haijunbot.haijunbot_utils.globals as G

                    title = f"[bold cyan]{(G.get_current_agent_name() + ' · ') if G.get_current_agent_name() else ''}{self.model.model_name or 'LLM'} Task Summary[/bold cyan]"
                    PrettyOutput.print_markdown(
                        ret, title=title, border_style="bright_green"
                    )
                except Exception:
                    # If formatting fails, fall back to simple printing
                    PrettyOutput.auto_print(f"📋 Task summary:\n{ret}")

            # Non-critical path: broadcast the summary-completed event (for logging, monitoring, etc.)
            try:
                self.event_bus.emit(
                    AFTER_SUMMARY,
                    agent=self,
                    summary=result,
                )
            except Exception as e:
                save_exception(
                    e, module="haijunbot_agent.__init__", function="_complete_task"
                )
                pass

            # Critical path: call task_analyzer and memory_manager directly

        # Print the original user input regardless of whether a summary is needed, to help the user distinguish multiple tasks
        if self.non_interactive:
            if self.original_user_input:
                PrettyOutput.auto_print(f"📝 Original task input:\n{self.original_user_input}")

        try:
            self.memory_manager._ensure_memory_prompt(
                agent=self,
                auto_completed=auto_completed,
                need_summary=self.need_summary,
            )
        except Exception as e:
            save_exception(e, module="haijunbot_agent.__init__", function="_complete_task")
            pass

        # Non-critical path: broadcast the task-completed event (for logging, monitoring, etc.)
        try:
            self.event_bus.emit(
                TASK_COMPLETED,
                agent=self,
                auto_completed=auto_completed,
                need_summary=self.need_summary,
            )
        except Exception as e:
            save_exception(e, module="haijunbot_agent.__init__", function="_complete_task")
            pass

        # If there are memory tags, add a hint to the returned result
        memory_tags = self.get_memory_tags()
        if memory_tags:
            tags_str = ", ".join(f"`{tag}`" for tag in memory_tags)
            memory_hint = f"\n\n💡 **Memory tag hint**: this task produced the following memory tags: {tags_str}\nYou can use the `memory` tool (action=retrieve) to retrieve related memories via these tags for more details."
            result = result + memory_hint

        # Audit: record the task-completed event (zero overhead when disabled)
        self._audit_log(
            "task_completed",
            auto_completed=auto_completed,
            need_summary=self.need_summary,
            result=result[:500],
        )

        return result

    def make_default_addon_prompt(self, need_complete: bool) -> str:
        """Generate the addon prompt.

        Args:
            need_complete: whether the task should be completed

        """
        # Prefer PromptManager to keep the logic centralized
        try:
            return self.prompt_manager.build_default_addon_prompt(need_complete)
        except Exception as e:
            save_exception(
                e, module="haijunbot_agent.__init__", function="make_default_addon_prompt"
            )
            pass

        # Structured system instructions (fallback plan)
        action_handlers = ", ".join([handler.name() for handler in self.output_handler])

        # Task completion hint
        complete_prompt = (
            f"- If the entire task is complete, only output {ot('!!!COMPLETE!!!')} and nothing else; a task summary will be asked in a later interaction."
            if need_complete and self.auto_complete
            else ""
        )

        # Do not inject text JSON/action-list instructions when native function calling is active
        if self._native_active():
            tool_lines = (
                "- When an operation is needed, make a tool call directly; tool names and arguments follow the tool definitions given in the current context"
                "\n        - One or more independent tools may be called at once; if there are dependencies, wait for the previous result before calling the next"
            )
            actions_line = ""
        else:
            tool_registry = self.get_tool_registry()
            memory_prompts = self.memory_manager.add_memory_prompts_to_addon(
                "", tool_registry
            )
            tool_lines = (
                "- Tool calls output JSON objects directly, without any label wrapping"
                "\n        - One or more tools may be called at once, but the tools must be **independent of each other**"
                " (the result/side effect of the former cannot be input to the latter); when there are dependencies, call the depended-on tool first, then wait for its result before calling the next"
            )
            actions_line = f"- Available operations: {action_handlers}{memory_prompts}"

        addon_prompt = f"""
<system_prompt>
    First assess whether the entire task is complete:

    - If complete:
        {complete_prompt if complete_prompt else "- State the completion reason and stop; do not make new tool calls"}
    - If not complete, keep pushing the next step:
        - When writing large content such as files, do not write it all at once; write in multiple parts to avoid being truncated by length limits
        - When requirements or information are unclear, ask the user for clarification first
        - After 5 consecutive failures, stop and ask the user how to continue
        {tool_lines}
        {actions_line}

    Supplementary: if the task of the current phase is complete and the previous context is of little value, you may output {ot("!!!SUMMARY!!!")} to trigger compression and clear history, so a new phase can begin.
</system_prompt>

Please continue.
"""

        return addon_prompt

    def run(self, user_input: Union[str, List[ContentBlock]]) -> Any:
        """Process user input and execute the task

        Args:
            user_input: task description or request, supporting plain text or multimodal content

        Returns:
            str|Dict: the task summary report or the message to send

        Notes:
            1. This is the Agent's main run loop
            2. Handles the complete task lifecycle
            3. Includes error handling and recovery logic
            4. Automatically loads relevant methodology (if first run)
        """
        # Set the tmux tiled layout (only once, on the first run)
        if not hasattr(Agent, "_tmux_layout_set"):
            Agent._tmux_layout_set = False
        if not Agent._tmux_layout_set:
            Agent._tmux_layout_set = True
            try:
                if "TMUX" in os.environ:
                    # In a tmux environment, set the current window to a tiled layout
                    import subprocess

                    subprocess.run(
                        ["tmux", "select-layout", "tiled"],
                        check=True,
                        timeout=5,
                    )
            except Exception:
                # Fail silently; does not affect normal use
                pass

        # If the system prompt needs deferred optimization, optimize it on the first run
        if (
            self._optimize_system_prompt_on_first_run
            and not self._system_prompt_optimized
        ):
            # Check whether user_input has content
            has_content = False
            text_input = ""
            if user_input:
                if isinstance(user_input, str):
                    if user_input.strip():
                        has_content = True
                        text_input = user_input.strip()
                else:
                    # Multimodal content
                    text_parts = [
                        b.get("text", "") for b in user_input if b.get("type") == "text"
                    ]
                    text_input = "\n".join(text_parts).strip()
                    if text_input:
                        has_content = True

            if has_content:
                self.optimize_system_prompt(text_input)
                self._system_prompt_optimized = True
        # Generate an extra explanation per the current mode so the LLM can sense the execution strategy
        # Deferred import of CodeAgent to avoid circular dependencies
        try:
            from haijunbot.haijunbot_code_agent.code_agent import CodeAgent
        except ImportError as e:
            raise RuntimeError(
                "CodeAgent could not be imported. Please ensure haijunbot_code_agent is installed correctly."
            ) from e

        try:
            # Save the original task goal (for context retention during long runs)
            # Only set the original task goal on the first run, so later inputs in interactive mode do not overwrite it
            if not self.original_user_input:
                self.original_user_input = user_input

            # Audit: record the user input event (zero overhead when disabled)
            if isinstance(user_input, str):
                input_text = user_input
            else:
                input_text = "\n".join(
                    b.get("text", "") for b in user_input if b.get("type") == "text"
                )
            self._audit_log("user_input", user_input=input_text[:500])

            # For CodeAgent instances, skip registration; CodeAgent.run manages it
            if not isinstance(self, CodeAgent):
                set_current_agent(self.name, self)  # Mark the agent as started

                # Generic Agent request classification (only on the first run when classification is enabled)
                if (
                    self.first
                    and is_enable_request_classification()
                    and not self.quick_mode
                ):
                    from haijunbot.haijunbot_agent.agent_prompts import (
                        classify_user_request,
                        get_system_prompt,
                    )

                    self._classify_and_switch_model(
                        user_input, classify_user_request, get_system_prompt
                    )

            non_interactive_note = ""
            if getattr(self, "non_interactive", False):
                non_interactive_note = (
                    "\n\n[System Note]\n"
                    "This session is in **non-interactive mode**:\n"
                    "- After giving a clear and executable detailed plan in PLAN mode, you should **automatically enter EXECUTE mode to carry out the plan**, without waiting for extra user confirmation;\n"
                    "- In EXECUTE mode, keep a step-by-step small-commit and revertible strategy, but do not repeatedly ask the user 'continue?';\n"
                    "- If information is severely insufficient, you may autonomously gather the necessary analysis in RESEARCH mode instead of waiting indefinitely for user input.\n"
                )

                # In non-interactive mode, no longer auto-set pin_content

            # Append the non-interactive note to the user input
            enhanced_input: Union[str, List[ContentBlock]]
            if non_interactive_note:
                if isinstance(user_input, str):
                    enhanced_input = user_input + non_interactive_note
                else:
                    # For multimodal content, append the note as a text block at the end
                    enhanced_input = user_input + cast(
                        List[ContentBlock],
                        [{"type": "text", "text": non_interactive_note}],
                    )
            else:
                enhanced_input = user_input

            # Set session.prompt first, so _first_run() can access the user input
            # Note: the activated rules have not been added yet; rules will be appended later
            self.session.prompt = enhanced_input

            # First-run initialization (including auto rule selection)
            # Must run before fetching the rules content, otherwise the rule index would be overwritten by wrong rule content
            if self.first:
                self._first_run()
                # Quick mode hint
                if self.quick_mode:
                    from haijunbot.haijunbot_utils.output import PrettyOutput

                    PrettyOutput.auto_print(
                        "⚡ Quick mode enabled: skipping task classification, rule loading, and context recommendations"
                    )

            # Prepend the loaded rule content to the user input
            active_rules_content = self.rules_manager.get_injectable_rules_content()
            if active_rules_content:
                enhanced_input = (
                    f"<rules>\n{active_rules_content}\n</rules>\n\n{enhanced_input}"
                )
                # Update session.prompt to include the rule content
                self.session.prompt = enhanced_input

            # Critical path: call memory_manager directly to reset the task state
            try:
                self.memory_manager._on_task_started(
                    agent=self,
                    name=self.name,
                    description=self.description,
                    user_input=self.session.prompt,
                )
            except Exception as e:
                save_exception(e, module="haijunbot_agent.__init__", function="run")
                pass

            # Non-critical path: broadcast the task-started event (for logging, monitoring, etc.)
            try:
                self.event_bus.emit(
                    TASK_STARTED,
                    agent=self,
                    name=self.name,
                    description=self.description,
                    user_input=self.session.prompt,
                )
            except Exception as e:
                save_exception(e, module="haijunbot_agent.__init__", function="run")
                pass

            return self._main_loop()

        finally:
            if not isinstance(self, CodeAgent):
                clear_current_agent()
            # Graceful exit: notify the daemon to clean up memory (no disk write)
            self._notify_session_daemon_quit()

    def analysis(self, satisfaction_feedback: str = "") -> None:
        """Run task analysis directly (skip user confirmation)

        This method provides a direct interface for task analysis that can immediately run the analysis flow,
        including saving memory, generating methodology, etc., without user confirmation.

        Args:
            satisfaction_feedback: satisfaction feedback content (optional).
                - If provided, the feedback is used directly for the analysis
                - If empty, no feedback is collected and the analysis runs directly

        Examples:
            >>> agent.analysis()  # analyze directly, no feedback
            >>> agent.analysis("User satisfied")  # analysis with feedback

        Notes:
            - This method skips the user confirmation step
            - Suitable for automation scenarios or programmatic invocation
            - For user confirmation and feedback collection, use task_analyzer.trigger_task_analysis()
        """
        self.task_analyzer.analysis_task(satisfaction_feedback)

    def _main_loop(self) -> Any:
        """Main run loop"""
        # Delegate to the dedicated run loop class to keep behavior consistent
        loop = AgentRunLoop(self)
        self._agent_run_loop = loop  # store the reference so other methods can access it
        return loop.run()

    def set_non_interactive(self, value: bool) -> None:
        """Set non-interactive mode and manage the auto-complete state.

        When entering non-interactive mode, auto-complete is enabled automatically;
        when leaving non-interactive mode, the original auto-complete values are restored.

        Args:
            value: whether non-interactive mode is enabled
        """
        # Save the original values of auto_complete and need_summary (only on the first set)
        if not hasattr(self, "_auto_complete_backup"):
            self._auto_complete_backup = self.auto_complete
        if not hasattr(self, "_need_summary_backup"):
            self._need_summary_backup = self.need_summary

        # Set non-interactive mode (only an Agent instance attribute, not written to env vars or global config)
        self.non_interactive = value

        # Keep the SessionManager's non-interactive state in sync
        self.session.non_interactive = value

        # Adjust auto_complete and need_summary based on the non_interactive value
        if value:  # Entering non-interactive mode
            self.auto_complete = True
            # Disable summaries when entering non-interactive mode (avoid triggering a summary on auto-complete)
            self.need_summary = False
        else:  # Leaving non-interactive mode
            # Restore the original values of auto_complete and need_summary
            self.auto_complete = self._auto_complete_backup
            self.need_summary = self._need_summary_backup
            # Clean up the backup to avoid state pollution
            delattr(self, "_auto_complete_backup")
            delattr(self, "_need_summary_backup")

    def _handle_run_interrupt(
        self, current_response: str
    ) -> Optional[Union[Any, "LoopAction"]]:
        """Handle an interrupt during a run

        Returns:
            None: no interrupt, or the current response may continue after the interrupt
            Any: the final result to return
            LoopAction.SKIP_TURN: skip the current response after the interrupt and start the next loop immediately
        """
        if not get_interrupt():
            return None

        set_interrupt(False)

        # Native tool call path: after an interrupt, discard the pending tools of this round that have not executed,
        # so the run_loop main loop does not still execute these tool_calls after recovering from the interrupt.
        # (The model re-decides next round based on the user's supplementary info, instead of reusing the interrupted output)
        self._pending_native_tool_calls = None

        # When interrupted, if currently non-interactive, switch to interactive mode immediately (before getting user input)
        if self.non_interactive:
            self.set_non_interactive(False)

        user_input = self._multiline_input(
            "Interrupted during model interaction; please enter your intervention information", False
        )
        # Broadcast the interrupt event (includes user input, which may be an empty string)
        try:
            self.event_bus.emit(
                INTERRUPT_TRIGGERED,
                agent=self,
                current_response=current_response,
                user_input=user_input,
            )
        except Exception as e:
            save_exception(
                e, module="haijunbot_agent.__init__", function="_handle_run_interrupt"
            )
            pass

        self.run_input_handlers_next_turn = True

        if not user_input:
            # User input is empty; complete the task
            # Leave auto-complete mode to prevent _execute_auto_complete from calling _complete_task again
            self.return_control_on_auto_complete = True
            return self._complete_task(auto_completed=False)

        # Process the input (including shell commands, etc.), giving input_handler a chance to handle it
        processed_input = self._process_input(user_input)

        # If the input handler returned an empty string or signaled return, it was already handled (e.g. a shell command)
        if not processed_input or self._last_handler_returned:
            # The input was already handled (e.g. a shell command was executed); no need to continue
            return LoopAction.SKIP_TURN

        if any(handler.can_handle(current_response) for handler in self.output_handler):
            if self.confirm_callback("A tool call was detected. Continue executing the tool call?", False):
                self.session.prompt = join_prompts(
                    [
                        f"The user interrupted the operation; the user's supplementary info is: {processed_input}",
                        "The user allows continuing the tool call.",
                    ]
                )
                return None  # Continue executing the tool call
            else:
                self.session.prompt = join_prompts(
                    [
                        f"The user interrupted the operation; the user's supplementary info is: {processed_input}",
                        "A tool call was detected, but the user refused execution. Reconsider the next step based on the user's supplementary info.",
                    ]
                )
                return LoopAction.SKIP_TURN  # Request the main loop to continue
        else:
            self.session.prompt = f"The user interrupted the operation; the user's supplementary info is: {processed_input}"
            return LoopAction.SKIP_TURN  # Request the main loop to continue

    def _get_next_user_action(self) -> Union[str, "LoopAction"]:
        """Get the user's next action

        Returns:
            LoopAction.CONTINUE or LoopAction.COMPLETE (compatible with the legacy string values "continue"/"complete")
        """
        user_input = self._multiline_input(
            f"{self.name}: Enter input (Ctrl+C to end the current task)", False
        )

        if user_input:
            # Process the input (including shell commands, etc.), giving input_handler a chance to handle it
            processed_input = self._process_input(user_input)

            # If the input handler returned an empty string or signaled return, it was already handled (e.g. a shell command)
            if not processed_input or self._last_handler_returned:
                # The input was already handled (e.g. a shell command was executed); keep getting the next input
                return LoopAction.CONTINUE

            self.session.prompt = processed_input
            # A new task mid-session: hard-trigger possibly relevant rules and wrap them into this context
            self._hard_trigger_rules(ensure_str(processed_input))
            # When a repeated response is detected, append a no-repeat hint at the end of the prompt
            if self._repeat_detected:
                self.session.prompt = join_prompts(
                    [
                        self.session.prompt,
                        "Do not repeat the previous answer; please give a different answer.",
                    ]
                )
                self._repeat_detected = False
                self._repeat_escalation_level = 0
            # Use the explicit action signal, keeping the return type annotation for compatibility
            return LoopAction.CONTINUE
        else:
            return LoopAction.COMPLETE

    def _first_run(self) -> None:
        """First-run initialization"""
        # If there are too many tools, use AI to filter them
        if self.session.prompt:
            self._filter_tools_if_needed(ensure_str(self.session.prompt))

        # Prepare the memory tag hint
        memory_tags_prompt = self.memory_manager.prepare_memory_tags_prompt()

        # Actively retrieve historical memories relevant to the current task
        if self.session.prompt:
            memory_context_prompt = self.memory_manager.prepare_memory_context_prompt(
                ensure_str(self.session.prompt),
                retrieval_budget=self._get_memory_retrieval_budget(),
            )
        else:
            memory_context_prompt = ""

        # Skip auto rule selection in quick mode
        if not self.quick_mode:
            # Auto-select and load rules (if the user did not specify rules and auto rule selection is enabled)
            if self.session.prompt and self._enable_auto_rule_select:
                self.auto_select_and_load_rules(ensure_str(self.session.prompt))

        # Add the memory tag hint
        if memory_tags_prompt:
            self.session.prompt = f"{self.session.prompt}{memory_tags_prompt}"

        # Add the actively retrieved relevant memories
        if memory_context_prompt:
            self.session.prompt = f"{self.session.prompt}{memory_context_prompt}"

        # Mark that first-run initialization has executed (used by the first-round no-tool-call detection)
        self._first_run_occurred = True
        self.first = False

    def _get_memory_retrieval_budget(self) -> int:
        """Compute the token cap for memory retrieval injection based on the layered context budget.

        Total context budget = model max input tokens × usage ratio (with headroom reserved), then
        allocated by the memory_retrieval layer share. If any step fails, fall back to the configured
        fixed budget, ensuring memory injection is never interrupted by a budget computation error.
        """
        try:
            from haijunbot.haijunbot_utils.config import (
                calculate_layer_token_budget,
                get_context_budget_usage_ratio,
                get_context_memory_retrieval_budget,
                get_max_input_token_count,
            )

            total_budget = int(
                get_max_input_token_count() * get_context_budget_usage_ratio()
            )
            budgets = calculate_layer_token_budget(total_budget)
            return int(budgets.get("memory_retrieval", 0))
        except Exception:
            from haijunbot.haijunbot_utils.config import get_context_memory_retrieval_budget

            return get_context_memory_retrieval_budget()

    def _create_temp_model(
        self, system_prompt: str = "", force_model_type: Optional[str] = None
    ) -> BasePlatform:
        """Create a temporary model instance for one-off tasks (delegated to ModelSwitcher)"""
        return self._model_switcher.create_temp_model(
            system_prompt=system_prompt,
            force_model_type=force_model_type,
        )

    def _has_user_specified_rules(self) -> bool:
        """Determine whether the user has specified rules

        Ways the user can specify rules:
        1. The rule_names CLI argument
        2. The input tag '<rule:xxx>'

        Returns:
            bool: True if the user has specified rules (non-default rules)
        """
        from haijunbot.haijunbot_utils.config import get_default_rule_names
        from haijunbot.haijunbot_agent.builtin_input_handler import extract_tags_from_text

        # Default rules (from the default_rule_names config, not treated as user-specified)
        default_rules = set(get_default_rule_names())

        # Check whether loaded_rule_names contains any non-default rule
        for rule_name in self.loaded_rule_names:
            if rule_name not in default_rules:
                return True

        # Check whether the user input contains a '<rule:xxx>' tag
        if self.session.prompt:
            tags = extract_tags_from_text(self.session.prompt)
            if any(tag.startswith("rule:") for tag in tags):
                return True

        return False

    def auto_select_and_load_rules(self, task_description: str) -> None:
        """Automatically select and load rules based on the task description (at most 3)

        Args:
            task_description: task description string
        """
        try:
            # If the user has specified rules, skip auto selection
            if self._has_user_specified_rules():
                PrettyOutput.auto_print("ℹ️  The user has specified rules; skipping auto rule selection")
                return

            # Call the rule-matching method (supports local + remote search)
            selected_rules = self.rules_manager.match_rules_to_task(task_description)

            # If rules were selected successfully, activate them
            if selected_rules:
                # Check for the "no rules needed" marker
                if selected_rules == ["__NO_RULES_NEEDED__"]:
                    PrettyOutput.auto_print("✅ The task is simple; no specific rules are needed")
                    return

                # Iterate over the rule list and activate each
                for rule_name in selected_rules:
                    # Use the load_rule method to load the rule (it checks for duplicates and merges automatically)
                    if self.rules_manager.load_rule(rule_name):
                        # Print the full rule file path to avoid the Agent mistaking "scope:relative path"
                        # for the file_path passed directly to load_rule
                        rule_path = self.rules_manager.get_rule_file_path(rule_name)
                        display = (
                            rule_path if rule_path and rule_path != "--" else rule_name
                        )
                        PrettyOutput.auto_print(f"✅ Auto-selected rule based on the task: {display}")
                    else:
                        PrettyOutput.auto_print(f"ℹ️  Rule already exists or failed to activate: {rule_name}")
        except Exception as e:
            # Rule selection failure does not affect the main flow; handle silently
            PrettyOutput.auto_print(f"⚠️  Auto rule selection failed: {e}")

    def _wrap_loaded_rules(self, text: str) -> str:
        """Wrap the currently loaded rules as a <rules> prefix (replacing the old block), returning the new text."""
        try:
            import re

            content = self.rules_manager.get_injectable_rules_content()
            if not content:
                return text
            block = f"<rules>\n{content}\n</rules>"
            cleaned = re.sub(r"<rules>.*?</rules>", "", text, flags=re.S).strip()
            return block + "\n\n" + cleaned
        except Exception:
            return text

    def _hard_trigger_rules(self, task: str) -> None:
        """Hard trigger: before handling a new task, use a cheap judgment to force-load possibly relevant rules.

        Auto selection for the first task has already been done in _first_run; this handles new tasks that
        appear mid-session, ensuring rules/tracks are "loaded on a ≥1% hit" and wrapping loaded rules into this task's context.
        """
        try:
            if getattr(self, "quick_mode", False) or not getattr(
                self, "_enable_auto_rule_select", False
            ):
                return
            if not task or len(task.strip()) < 40:
                return
            picked = self.rules_manager.match_task_cheap(task)
            if not picked:
                return
            newly = []
            for rule_name in picked:
                if rule_name in (self.loaded_rule_names or []):
                    continue
                if self.rules_manager.load_rule(rule_name):
                    newly.append(rule_name)
            if newly:
                PrettyOutput.auto_print("⚡ Hard-trigger loaded rules: " + ", ".join(newly))
                self.session.prompt = self._wrap_loaded_rules(
                    ensure_str(self.session.prompt or task)
                )
        except Exception as e:
            PrettyOutput.auto_print(f"⚠️  Hard-trigger rule loading failed: {e}")

    def _filter_tools_if_needed(self, task: str) -> None:
        """If the tool count exceeds the threshold, use the model to filter relevant tools

        Note: only user-defined tools are filtered; built-in tools are not filtered (always kept)
        """
        tool_registry = self.get_tool_registry()
        if not isinstance(tool_registry, ToolRegistry):
            return

        all_tools = tool_registry.get_all_tools()
        threshold = get_tool_filter_threshold()
        if len(all_tools) <= threshold:
            return

        # Get user-defined tools (non built-in); only these are filtered
        custom_tools = tool_registry.get_custom_tools()
        if not custom_tools:
            # No user-defined tools, no need to filter
            return

        # Build the prompt for tool selection (only user-defined tools)
        tools_prompt_part = ""
        tool_names = []
        tool_desc_by_name = {}
        for i, tool in enumerate(custom_tools, 1):
            tool_names.append(tool["name"])
            tool_desc_by_name[tool["name"]] = tool["description"]
            tools_prompt_part += f"{i}. {tool['name']}: {tool['description']}\n"

        selection_prompt = f"""
User task:
<task>
{task}
</task>

Available tool list:
<tools>
{tools_prompt_part}
</tools>

Based on the user task, select the most relevant tools.
Return only the numbers of the selected tools, separated by commas. For example: 1, 5, 12
"""
        PrettyOutput.auto_print(
            f"ℹ️ More than {threshold} tools; filtering relevant tools with AI..."
        )
        # Broadcast the tool-filter-started event
        try:
            self.event_bus.emit(
                BEFORE_TOOL_FILTER,
                agent=self,
                task=task,
                total_tools=len(all_tools),
                threshold=threshold,
            )
        except Exception as e:
            save_exception(
                e, module="haijunbot_agent.__init__", function="_filter_tools_if_needed"
            )
            pass

        # Use a temporary model instance to call the model, avoiding pollution of the history
        try:

            def _select_with_normal_model() -> str:
                """Existing flow: use a temporary model to select tool numbers."""
                temp_model = self._create_temp_model("You are an assistant that helps filter tools.")
                return temp_model.chat_until_success(selection_prompt)

            # Prefer the structured evaluation model for candidate selection: it only accepts the JSON
            # protocol and cannot consume natural-language prompts, so decide_choice converts the protocol.
            # When no evaluation model is configured or the call fails, decide_choice internally falls back to lambda: None.
            picked_tools = decide_choice(
                task,
                {name: desc for name, desc in tool_desc_by_name.items()},
                lambda: None,
                max_select=len(tool_names),
            )
            if picked_tools:
                selected_tool_names = sorted(set(picked_tools))
            else:
                # When the structured evaluation model selects no tools (unconfigured/failed/no match), use the existing flow.
                # Note: decide() cannot be used here, because selection_prompt is a natural-language protocol that
                # the structured evaluation model cannot consume; it would just fail once for nothing.
                selected_tools_str = _select_with_normal_model()

                # Parse the response and filter tools
                selected_indices = [
                    int(i.strip()) for i in re.findall(r"\d+", selected_tools_str)
                ]
                selected_tool_names = [
                    tool_names[i - 1]
                    for i in selected_indices
                    if 0 < i <= len(tool_names)
                ]

            if selected_tool_names:
                # Remove duplicates
                selected_tool_names = sorted(list(set(selected_tool_names)))
                # Merge built-in tool names with the filtered user-defined tool names
                builtin_names = list(tool_registry._builtin_tool_names)
                final_tool_names = sorted(
                    list(set(builtin_names + selected_tool_names))
                )
                tool_registry.use_tools(final_tool_names)
                # Re-set the system prompt with the filtered tool list
                self._setup_system_prompt()
                PrettyOutput.auto_print(
                    f"✅ Filtered out {len(selected_tool_names)} relevant tools: {', '.join(selected_tool_names)}"
                )
                # Broadcast the tool-filtered event
                try:
                    self.event_bus.emit(
                        TOOL_FILTERED,
                        agent=self,
                        task=task,
                        selected_tools=selected_tool_names,
                        total_tools=len(all_tools),
                        threshold=threshold,
                    )
                except Exception as e:
                    save_exception(
                        e,
                        module="haijunbot_agent.__init__",
                        function="_filter_tools_if_needed",
                    )
                    pass
            else:
                PrettyOutput.auto_print("⚠️ AI selected no relevant tools; using all tools.")
                # Broadcast the tool-filtered event (no filtering result)
                try:
                    self.event_bus.emit(
                        TOOL_FILTERED,
                        agent=self,
                        task=task,
                        selected_tools=[],
                        total_tools=len(all_tools),
                        threshold=threshold,
                    )
                except Exception as e:
                    save_exception(
                        e,
                        module="haijunbot_agent.__init__",
                        function="_filter_tools_if_needed",
                    )
                    pass

        except Exception as e:
            PrettyOutput.auto_print(f"❌ Tool filtering failed: {e}; using all tools.")

    def _check_and_organize_memory(self) -> None:
        """
        Check the memory store state and, if the conditions are met, prompt the user to organize it.
        Checked only once per day.
        """
        try:
            # Check project memory
            self._perform_memory_check("project_long_term", Path(".haijunbot"), "project")
            # Check global memory
            self._perform_memory_check(
                "global_long_term",
                Path(get_data_dir()),
                "global",
            )
        except Exception as e:
            PrettyOutput.auto_print(f"⚠️ An unexpected error occurred while checking the memory store: {e}")

    def _perform_memory_check(
        self, memory_type: str, base_path: Path, scope_name: str
    ) -> None:
        """Run the memory check and organization for a specific scope"""
        check_file = base_path / ".last_memory_organizer_check"
        now = datetime.datetime.now()

        if check_file.exists():
            try:
                last_check_time = datetime.datetime.fromisoformat(
                    check_file.read_text()
                )
                if (now - last_check_time).total_seconds() < 24 * 3600:
                    return  # Already checked within 24 hours
            except (ValueError, FileNotFoundError):
                # Invalid file content or the file was deleted during read; continue with the check
                pass

        # Update the check time immediately to prevent concurrent or repeated checks
        base_path.mkdir(parents=True, exist_ok=True)
        check_file.write_text(now.isoformat())

        organizer = MemoryOrganizer()
        # NOTE: use protected methods to avoid duplicating the logic
        memories = organizer._load_memories(memory_type)

        if len(memories) < 200:
            return

        # NOTE: use protected methods to avoid duplicating the logic
        overlap_groups = organizer._find_overlapping_memories(memories, min_overlap=3)
        has_significant_overlap = any(groups for groups in overlap_groups.values())

        if not has_significant_overlap:
            return

        prompt = (
            f"Your '{scope_name}' memory store was detected to contain {len(memories)} memories,"
            f" and three or more memories with overlapping tags.\n"
            f"Do you want to organize the memory store now to optimize performance and relevance?"
        )
        if self.confirm_callback(prompt, False):
            PrettyOutput.auto_print(
                f"ℹ️ Starting to organize the '{scope_name}' ({memory_type}) memory store..."
            )
            organizer.organize_memories(memory_type)
        else:
            PrettyOutput.auto_print(f"ℹ️ Cancelled organizing the '{scope_name}' memory store.")
