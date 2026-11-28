"""
Input processing module
This module provides utilities for handling user input in the HaijunBot system.
Includes:
- Single-line input with history support
- Multi-line input with enhanced completion
- File path completion with fuzzy matching
- Custom key bindings for input control
"""

import base64
import json
import os
import sys
import threading
from abc import ABC
from abc import abstractmethod

from haijunbot.haijunbot_utils.output import PrettyOutput

# -*- coding: utf-8 -*-
from typing import Dict
from typing import Iterable
from typing import List
from typing import Any
from typing import Optional
from typing import Tuple
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

import wcwidth
from colorama import Fore
from colorama import Style as ColoramaStyle
from fuzzywuzzy import process
from prompt_toolkit import PromptSession
from prompt_toolkit.application import run_in_terminal
from prompt_toolkit.completion import CompleteEvent
from prompt_toolkit.completion import Completer
from prompt_toolkit.completion import Completion
from prompt_toolkit.completion import PathCompleter
from prompt_toolkit.document import Document
from prompt_toolkit.enums import DEFAULT_BUFFER
from prompt_toolkit.filters import has_focus
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.history import FileHistory
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.key_binding.key_processor import KeyPressEvent
from prompt_toolkit.styles import Style as PromptStyle

from haijunbot.haijunbot_utils.clipboard import copy_to_clipboard
from haijunbot.haijunbot_utils.config import get_data_dir
from haijunbot.haijunbot_utils.exception_utils import save_exception
from haijunbot.haijunbot_utils.config import get_replace_map
from haijunbot.haijunbot_utils.config import get_submit_keys
from haijunbot.haijunbot_utils.globals import get_message_history
from haijunbot.haijunbot_utils.tag import ot
from haijunbot.haijunbot_utils.utils import decode_output

# Import modules needed inside functions at the top of the file
# (Use aliases to avoid conflicts with built-in modules)
import os as _os
import subprocess as _subprocess
import shutil as _shutil

# Sentinel value to indicate that Ctrl+O was pressed
CTRL_O_SENTINEL = "__CTRL_O_PRESSED__"
# Sentinel value to indicate that Ctrl+X was pressed (exit program)
CTRL_X_SENTINEL = "__CTRL_X_PRESSED__"
# Sentinel prefix to indicate that Ctrl+F (fzf) inserted content should prefill next prompt
FZF_INSERT_SENTINEL_PREFIX = "__FZF_INSERT__::"
# Sentinel to request running fzf outside the prompt and then prefill next prompt
FZF_REQUEST_SENTINEL_PREFIX = "__FZF_REQUEST__::"
# Sentinel to request running fzf outside the prompt for all-files mode (exclude .git)
FZF_REQUEST_ALL_SENTINEL_PREFIX = "__FZF_REQUEST_ALL__::"
# Sentinel value to indicate that Ctrl+C was pressed
CTRL_C_SENTINEL = "__CTRL_C_PRESSED__"
# Sentinel value to indicate that Alt+T was pressed
CTRL_T_SENTINEL = "__ALT_T_PRESSED__"


def _gen_shell_cmd_for_terminal() -> str:
    """Generate shell command for terminal execution.

    This function generates appropriate shell commands based on the operating system.
    It's used both for Alt+T in CLI mode and for the Web frontend.

    Returns:
        Shell command string with appropriate interpreter (without any prefix).
    """
    try:
        if _os.name == "nt":
            # Prefer PowerShell if available, otherwise fallback to cmd
            for name in ("pwsh", "powershell", "cmd"):
                if name == "cmd" or _shutil.which(name):
                    if name == "cmd":
                        # Keep session open with /K and set env for spawned shell
                        return "cmd /K set terminal=1"
                    else:
                        # PowerShell or pwsh: set env then remain in session
                        return f"{name} -NoExit -Command \"$env:terminal='1'\""
        else:
            shell_path = os.environ.get("SHELL", "")
            if shell_path:
                base = os.path.basename(shell_path)
                if base:
                    return f"env terminal=1 {base}"
            for name in ("fish", "zsh", "bash", "sh"):
                if _shutil.which(name):
                    return f"env terminal=1 {name}"
            return "env terminal=1 bash"
    except Exception:
        return "env terminal=1 bash"
    # Fallback for all cases
    return "env terminal=1 bash"


def _detect_shell_interpreter(script: str) -> str:
    """Detect the appropriate interpreter based on the terminal command content.

    Args:
        script: Terminal command content

    Returns:
        Interpreter name: 'bash', 'powershell', 'cmd', etc.
    """
    lines = script.strip().splitlines()
    if not lines:
        return "bash"
    first_line = lines[0].strip()
    if _os.name == "nt":
        if first_line.startswith("powershell ") or first_line.startswith("pwsh "):
            return "powershell"
        if first_line.startswith("cmd "):
            return "cmd"
    else:
        if first_line.startswith("env "):
            parts = first_line.split()
            for part in parts:
                if part in ("bash", "zsh", "fish", "sh"):
                    return "bash"
    return "bash"


def execute_shell_in_terminal(agent: Any) -> None:
    """Open an interactive Shell terminal for the user.

    This function is shared by the `<Shell>` tag and the Alt+T/Ctrl+T shortcuts: it directly calls execute_script
    tool to execute terminal commands in interactive mode, rather than returning a line starting with `!` for the input handler to parse.

    Args:
        agent: Current Agent instance (used for tool call context)
    """
    script = _gen_shell_cmd_for_terminal()
    PrettyOutput.auto_print(f"🖥️ Opening terminal: {script}")
    try:
        from haijunbot.haijunbot_tools.registry import ToolRegistry

        ToolRegistry().handle_tool_calls(
            {
                "name": "execute_script",
                "want": "User executes commands in an interactive terminal",
                "arguments": {
                    "interpreter": _detect_shell_interpreter(script),
                    "script_content": script,
                    "execution_mode": "interactive",
                },
            },
            agent,
        )
    except Exception as e:
        save_exception(
            e, module="haijunbot_utils.input", function="execute_shell_in_terminal"
        )
        PrettyOutput.auto_print(f"❌ Failed to open terminal: {e}")


# Persistent hint marker for multiline input (shown only once across runs)
_MULTILINE_HINT_MARK_FILE = os.path.join(get_data_dir(), "multiline_enter_hint_shown")

# Completion usage stats file
COMPLETION_STATS_FILE = os.path.join(get_data_dir(), "completion_usage_stats.json")


def _load_completion_usage_stats() -> Dict[str, int]:
    """Load completion usage stats from JSON file."""
    try:
        if not os.path.exists(COMPLETION_STATS_FILE):
            return {}
        with open(COMPLETION_STATS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if not isinstance(data, dict):
                return {}
            # Filter out invalid entries
            return {
                k: v
                for k, v in data.items()
                if isinstance(k, str) and isinstance(v, int) and v > 0
            }
    except Exception:
        return {}


def _save_completion_usage_stats(stats: Dict[str, int]) -> None:
    """Save completion usage stats to JSON file."""
    try:
        os.makedirs(os.path.dirname(COMPLETION_STATS_FILE), exist_ok=True)
        with open(COMPLETION_STATS_FILE, "w", encoding="utf-8") as f:
            json.dump(stats, f, indent=2, ensure_ascii=False)
    except Exception:
        # Non-critical: ignore save failures
        pass


def _update_completion_usage(file_path: str) -> None:
    """Update usage count for a file path."""
    try:
        stats = _load_completion_usage_stats()
        stats[file_path] = stats.get(file_path, 0) + 1
        _save_completion_usage_stats(stats)
    except Exception:
        # Non-critical: ignore update failures
        pass


# Built-in command marker list (used for autocompletion and fzf)
BUILTIN_COMMANDS = [
    ("Summary", "Summarize"),
    ("Pin", "Pin/sticky content"),
    ("ClearPin", "Clear pinned content"),
    ("Clear", "Clear history"),
    ("Commit", "Commit code"),
    ("ToolUsage", "Tool usage instructions"),
    ("ReloadConfig", "Reload configuration"),
    ("SaveSession", "Save current session"),
    ("RestoreSession", "Restore session"),
    ("ListSessions", "List all sessions"),
    ("ListRule", "List all rules"),
    ("UnloadRule", "Unload loaded rules"),
    ("ClearRules", "Clear all loaded rules"),
    ("Quiet", "Unattended mode"),
    ("AutoComplete", "Hand over to user after autocompletion"),
    ("FixToolCall", "Fix tool call"),
    ("SwitchModelGroup", "Switch model group"),
    ("SwitchModel", "Switch model"),
    ("SwitchProxyNode", "Switch proxy node"),
    ("AddDir", "Add extra completion directory"),
    ("Btw", "Temporary chat"),
    ("PrintConfig", "Print global configuration"),
    ("SetConfig", "Modify global configuration"),
    ("Diff", "Show changes from start_commit to current"),
    ("Review", "Code review"),
    ("InstallTrack", "Install Track"),
    ("SubAgent", "Start sub-Agent to execute tasks"),
    ("SubCodeAgent", "Start sub-CodeAgent to execute code tasks"),
    ("Init", "Initialize project overview"),
    ("TestCase", "Generate requirement test cases"),
    ("QuickConfig", "Quickly configure LLM platform"),
    ("LLMAdd", "Add LLM configuration"),
    ("LLMDelete", "Delete LLM configuration"),
    ("LLMUpdate", "Update LLM configuration"),
    ("LLMGroupAdd", "Add model group"),
    ("LLMGroupDelete", "Delete model group"),
    ("LLMGroupUpdate", "Update model group"),
    ("LLMGroupSet", "Set current model group"),
    ("Shell", "Open Shell terminal"),
    ("SetMaxToken", "Set maximum input Token count"),
    # C2Rust commands
    ("C2RustConfig", "C2Rust configuration management"),
    ("C2RustRun", "C2Rust run migration"),
    ("C2RustVerify", "C2Rust verify feature alignment"),
    # Sec commands
    ("SecConfig", "Security scan configuration management"),
    ("SecAnalyze", "Analyze security issues from JSON"),
    ("SecHeuristic", "Heuristic security scan"),
    ("SecScan", "Execute security scan"),
    # Agent orchestration commands
    ("OrganizeAgents", "Batch orchestrate and create Agents"),
    # File operation commands
    ("Cat", "View file content"),
    # Git commands
    ("GitPush", "Push code to remote"),
]

_ADDITIONAL_COMPLETION_DIRS: List[str] = []
_ADDITIONAL_COMPLETION_DIRS_LOCK = threading.RLock()

# By default, add HaijunBot's builtin directory to the completion path (using __file__ as the anchor to locate the project root)
_PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
_BUILTIN_DIR = os.path.join(_PROJECT_ROOT, "builtin")
if os.path.isdir(_BUILTIN_DIR):
    _ADDITIONAL_COMPLETION_DIRS.append(_BUILTIN_DIR)


def add_additional_completion_dir(dir_path: str) -> bool:
    """Add a session-level extra completion directory."""
    normalized = os.path.abspath(os.path.expanduser(dir_path.strip()))
    if not normalized or not os.path.isdir(normalized):
        return False
    with _ADDITIONAL_COMPLETION_DIRS_LOCK:
        if normalized not in _ADDITIONAL_COMPLETION_DIRS:
            _ADDITIONAL_COMPLETION_DIRS.append(normalized)
    return True


def get_additional_completion_dirs() -> List[str]:
    """Get the extra completion directories added in the current session."""
    with _ADDITIONAL_COMPLETION_DIRS_LOCK:
        return list(_ADDITIONAL_COMPLETION_DIRS)


def _scan_files_under_dir(
    base_dir: str,
    exclude_git: bool = False,
    max_files: int = 10000,
    use_absolute_path: bool = False,
) -> List[str]:
    """Scan files under the specified directory, with directory prefixes to avoid name ambiguity.

    Args:
        base_dir: Directory to scan
        exclude_git: Whether to exclude the .git directory
        max_files: Maximum number of files
        use_absolute_path: Whether to use absolute paths (default False, use relative paths)
    """
    files: List[str] = []
    try:
        base_dir_abs = _os.path.abspath(base_dir)
        display_prefix = _os.path.basename(base_dir_abs.rstrip(_os.sep)) or base_dir_abs
        for root, dirs, fnames in _os.walk(base_dir_abs, followlinks=False):
            if exclude_git:
                dirs[:] = [
                    d
                    for d in dirs
                    if d
                    not in {
                        ".git",
                        "__pycache__",
                        ".pytest_cache",
                        ".mypy_cache",
                        ".ruff_cache",
                        "node_modules",
                        "target",
                    }
                ]
            for name in fnames:
                abs_path = _os.path.join(root, name)
                if use_absolute_path:
                    files.append(abs_path)
                else:
                    rel_path = _os.path.relpath(abs_path, base_dir_abs)
                    files.append(_os.path.join(display_prefix, rel_path))
                if len(files) >= max_files:
                    return files
    except Exception:
        return []
    return files


def _merge_unique_paths(*path_groups: List[str]) -> List[str]:
    """Merge and deduplicate path lists in order."""
    merged: List[str] = []
    seen = set()
    for group in path_groups:
        for path in group:
            if path not in seen:
                seen.add(path)
                merged.append(path)
    return merged


class InputProviderTimeoutError(TimeoutError):
    """The input provider timed out waiting for user input."""


class InputProviderDisconnectedError(RuntimeError):
    """The remote session corresponding to the input provider has disconnected."""


class InputProvider(ABC):
    """User input provider abstraction."""

    @abstractmethod
    def get_multiline_input(
        self,
        tip: str,
        preset: Optional[str] = None,
        preset_cursor: Optional[int] = None,
    ) -> str:
        raise NotImplementedError

    def inject_prompt(self, prompt: str) -> None:
        """Inject a prompt into the next input (default empty implementation, subclasses may override)."""
        pass


class CLIInputProvider(InputProvider):
    """Default local CLI input provider, reusing the existing prompt_toolkit implementation."""

    def __init__(self) -> None:
        self._injected_prompts: list = []
        self._inject_lock = threading.Lock()
        # Global buffer used to inject content while waiting for input
        self._injected_buffer: Optional[str] = None
        self._is_prompting = False
        self._prompting_thread_id: Optional[int] = None

    def inject_prompt(self, prompt: str) -> None:
        """Inject a prompt into the next input (uniformly uses the global buffer)"""
        from haijunbot.haijunbot_utils.globals import add_input_buffer

        # Add to the global buffer (primary mechanism)
        add_input_buffer(prompt)

        # Backward compatibility: also maintain the old injection list (used for interruption while waiting for input)
        with self._inject_lock:
            self._injected_prompts.append(prompt)

            # If currently waiting for input, write to the local buffer and send a signal to interrupt
            if self._is_prompting and self._prompting_thread_id is not None:
                # Write the injected content to the local buffer
                if self._injected_buffer is None:
                    self._injected_buffer = prompt
                else:
                    self._injected_buffer += "\n" + prompt

                # Send a thread-level SIGINT signal to interrupt input
                try:
                    import signal

                    if hasattr(signal, "pthread_kill"):
                        # Validate whether the thread ID is valid (check if it is an active thread of the current process)
                        import threading

                        active_threads = {t.ident for t in threading.enumerate()}
                        if self._prompting_thread_id in active_threads:
                            signal.pthread_kill(
                                self._prompting_thread_id, signal.SIGINT
                            )
                except Exception:
                    # Windows or other platforms that do not support pthread_kill, or the thread no longer exists, fall back to deferred injection
                    pass

    def _consume_injected_prompts(self) -> Optional[str]:
        """Consume all injected prompts and return them merged"""
        with self._inject_lock:
            if not self._injected_prompts:
                return None
            prompts = self._injected_prompts.copy()
            self._injected_prompts.clear()
        return "\n".join(prompts)

    def _check_injected_buffer(self) -> Optional[str]:
        """Check and consume the contents of the global buffer"""
        with self._inject_lock:
            if self._injected_buffer is None:
                return None
            content = self._injected_buffer
            self._injected_buffer = None
            return content

    def get_multiline_input(
        self,
        tip: str,
        preset: Optional[str] = None,
        preset_cursor: Optional[int] = None,
    ) -> str:
        # Check the global buffer first (unified injection mechanism)
        from haijunbot.haijunbot_utils.globals import get_input_buffer

        buffered_messages = get_input_buffer()
        if buffered_messages:
            result = "\n".join(buffered_messages)
            return result

        # Check whether there are injected prompts (backward compatibility)
        injected = self._consume_injected_prompts()
        if injected is not None:
            return injected

        # Set the status flag and record the current thread ID
        with self._inject_lock:
            self._is_prompting = True
            self._prompting_thread_id = threading.get_ident()

        try:
            return _get_multiline_input_internal(
                tip, preset=preset, preset_cursor=preset_cursor, provider=self
            )
        finally:
            # Clear the status flag
            with self._inject_lock:
                self._is_prompting = False
                self._prompting_thread_id = None


_default_input_provider: InputProvider = CLIInputProvider()
_input_provider_lock = threading.RLock()
_input_providers: Dict[str, InputProvider] = {}


def register_input_provider(provider_id: str, provider: InputProvider) -> None:
    """Register a named input provider for remote sessions or specific Agents to bind to."""
    with _input_provider_lock:
        _input_providers[provider_id] = provider


def unregister_input_provider(provider_id: str) -> None:
    """Remove a named input provider; ignore if it does not exist."""
    with _input_provider_lock:
        _input_providers.pop(provider_id, None)


def set_default_input_provider(provider: InputProvider) -> None:
    """Set the global default input provider."""
    global _default_input_provider
    with _input_provider_lock:
        _default_input_provider = provider


def get_default_input_provider() -> InputProvider:
    """Get the current default input provider."""
    with _input_provider_lock:
        return _default_input_provider


def _resolve_input_provider_key(agent: Optional[Any]) -> Optional[str]:
    if agent is None:
        return None
    for attr_name in ("input_provider_key", "session_id"):
        try:
            value = getattr(agent, attr_name, None)
        except Exception:
            value = None
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def get_current_input_provider() -> InputProvider:
    """Get the input provider corresponding to the current Agent; fall back to the default CLI if not found."""
    agent = _get_current_agent_for_input()
    provider_key = _resolve_input_provider_key(agent)
    with _input_provider_lock:
        if provider_key and provider_key in _input_providers:
            return _input_providers[provider_key]
        return _default_input_provider


def _display_width(s: str) -> int:
    """Calculate the printable width of a string in the terminal (handles wide characters)."""
    try:
        w = 0
        for ch in s:
            cw = wcwidth.wcwidth(ch)
            if cw is None or cw < 0:
                # Fallback for unknown width chars (e.g. emoji on some terminals)
                cw = 1
            w += cw
        return w
    except Exception:
        return len(s)


def _calc_prompt_rows(prev_text: str) -> int:
    """
    Estimate how many terminal lines the previous prompt occupied.
    Considers the prompt prefix and soft wrapping across terminal columns.
    """
    try:
        cols = os.get_terminal_size().columns
    except Exception:
        cols = 80
    prefix = "👤 > "
    prefix_w = _display_width(prefix)

    lines = prev_text.splitlines()
    if not lines:
        lines = [""]
    # If the text ends with a newline, there is a visible empty line at the end.
    if prev_text.endswith("\n"):
        lines.append("")
    total_rows = 0
    for i, line in enumerate(lines):
        lw = _display_width(line)
        if i == 0:
            width = prefix_w + lw
        else:
            width = lw
        rows = max(1, (width + cols - 1) // cols)
        total_rows += rows
    return max(1, total_rows)


def _get_git_files() -> List[str]:
    """Get the list of files in the Git repository."""
    files = []
    try:
        r = _subprocess.run(
            ["git", "ls-files"],
            stdout=_subprocess.PIPE,
            stderr=_subprocess.PIPE,
            text=False,
        )
        if r.returncode == 0:
            files = [
                line for line in decode_output(r.stdout).splitlines() if line.strip()
            ]
    except Exception:
        files = []
    return files


def _get_additional_dir_files(
    exclude_git: bool = False, max_files: int = 10000
) -> List[str]:
    """Get the list of files in the added extra directories."""
    files: List[str] = []
    remaining = max_files
    for dir_path in get_additional_completion_dirs():
        if remaining <= 0:
            break
        current_files = _scan_files_under_dir(
            dir_path,
            exclude_git=exclude_git,
            max_files=remaining,
            use_absolute_path=True,
        )
        files.extend(current_files)
        remaining = max_files - len(files)
    return files


def _get_all_files(exclude_git: bool = False) -> List[str]:
    """Get the list of all files.

    Args:
        exclude_git: Whether to exclude the .git directory
    """
    files = []
    try:
        import os as _os

        for root, dirs, fnames in _os.walk(".", followlinks=False):
            if exclude_git:
                # Exclude .git directories
                dirs[:] = [d for d in dirs if d != ".git"]
            for name in fnames:
                files.append(_os.path.relpath(_os.path.join(root, name), "."))
            if len(files) > 10000:
                break
    except Exception:
        files = []
    return files


def _get_files_for_fzf(use_git: bool = True) -> List[str]:
    """Get the file list for FZF.

    Args:
        use_git: Whether to prefer the git file list (fall back to os.walk on failure)
    """
    if use_git:
        files = _get_git_files()
        if files:
            return _merge_unique_paths(
                files,
                _get_additional_dir_files(exclude_git=True),
            )
    return _merge_unique_paths(
        _get_all_files(exclude_git=True),
        _get_additional_dir_files(exclude_git=True),
    )


def _parse_fzf_payload(
    user_input: str, prefix: str
) -> Tuple[Optional[int], Optional[str]]:
    """Parse the FZF request payload.

    Args:
        user_input: User input, containing the FZF prefix and payload
        prefix: FZF prefix (such as FZF_REQUEST_SENTINEL_PREFIX)

    Returns:
        (cursor, text) tuple; returns (None, None) on parse failure
    """
    try:
        payload = user_input[len(prefix) :]
        sep_index = payload.find(":")
        cursor = int(payload[:sep_index])
        text = base64.b64decode(payload[sep_index + 1 :].encode("ascii")).decode(
            "utf-8"
        )
        return cursor, text
    except Exception:
        return None, None


def _run_fzf_for_selection(files: List[str], prompt_text: str) -> Optional[str]:
    """Run FZF to get the user's selection.

    Args:
        files: File list
        prompt_text: FZF prompt text

    Returns:
        The selected file path, or None on cancel or error
    """
    if _shutil.which("fzf") is None:
        PrettyOutput.auto_print("⚠️ fzf not detected, cannot open the file selector.")
        return None

    if not files:
        PrettyOutput.auto_print("ℹ️ No selectable files found.")
        return None

    # _get_fzf_completion_items automatically adds the complete BUILTIN_COMMANDS
    # so an empty list is passed here to avoid duplication
    specials: List[str] = []
    items = _get_fzf_completion_items(specials, files)
    proc = _subprocess.run(
        [
            "fzf",
            "--prompt",
            prompt_text,
            "--height",
            "40%",
            "--border",
        ],
        input="\n".join(items),
        stdout=_subprocess.PIPE,
        stderr=_subprocess.PIPE,
        text=True,
    )
    sel = proc.stdout.strip()
    return sel if sel else None


def _insert_file_path(
    text: str, cursor: int, path: str, symbol: str
) -> Tuple[str, int]:
    """Insert a file path into the text.

    Args:
        text: Original text
        cursor: Cursor position
        path: File path to insert
        symbol: Trigger symbol ('@' or '#')

    Returns:
        (new_text, new_cursor) tuple
    """
    text_before = text[:cursor]
    last_symbol = text_before.rfind(symbol)
    if last_symbol != -1 and " " not in text_before[last_symbol + 1 :]:
        # Replace @... or #... segment
        inserted = f"'{path}'"
        new_text = text[:last_symbol] + inserted + text[cursor:]
        new_cursor = last_symbol + len(inserted)
    else:
        # Plain insert
        inserted = f"'{path}'"
        new_text = text[:cursor] + inserted + text[cursor:]
        new_cursor = cursor + len(inserted)
    return new_text, new_cursor


def _clear_previous_prompt(text: str) -> None:
    """Clear the previous input line.

    Args:
        text: Previous input text
    """
    # Disable ANSI escape sequence clearing on Windows platform to avoid garbled text from terminal state confusion
    # Windows cmd.exe and some terminals do not support ANSI escape sequences by default; VT processing mode must be enabled
    if sys.platform == "win32":
        return

    try:
        rows_total = _calc_prompt_rows(text)
        for _ in range(rows_total):
            sys.stdout.write("\x1b[1A")  # Move cursor up one line
            sys.stdout.write("\x1b[2K\r")  # Clear the entire line
        sys.stdout.flush()
    except Exception as e:
        save_exception(
            e, module="haijunbot_utils.input", function="_clear_previous_prompt"
        )
        pass


def _multiline_hint_already_shown() -> bool:
    """Check whether the multi-line input prompt has already been displayed (persistent storage)."""
    try:
        return os.path.exists(_MULTILINE_HINT_MARK_FILE)
    except Exception:
        return False


def _mark_multiline_hint_shown() -> None:
    """Persistently store the state indicating that the multi-line input prompt has been displayed."""
    try:
        os.makedirs(os.path.dirname(_MULTILINE_HINT_MARK_FILE), exist_ok=True)
        with open(_MULTILINE_HINT_MARK_FILE, "w", encoding="utf-8") as f:
            f.write("1")
    except Exception:
        # Non-critical persistence failure; ignore to avoid breaking input flow
        pass


def get_single_line_input(
    tip: str, default: str = "", is_password: bool = False
) -> str:
    """
    Get single-line input with history support.

    Args:
        tip: Prompt text
        default: Default value
        is_password: Whether it is a password input (echoed as *)
    """
    is_non_interactive = _is_non_interactive_for_current_agent()
    if is_non_interactive:
        return default.strip()

    # Check whether in Gateway mode
    gateway = None
    GatewayInputRequest = None
    try:
        from haijunbot.haijunbot_gateway.events import (
            GatewayInputRequest as _GatewayInputRequest,
        )
        from haijunbot.haijunbot_gateway.manager import get_current_gateway

        gateway = get_current_gateway()
        GatewayInputRequest = _GatewayInputRequest
    except Exception:
        gateway = None

    if gateway is not None and GatewayInputRequest is not None:
        # Gateway mode: send input request to the frontend, wait for reconnection on disconnect
        import time

        while True:
            try:
                request = GatewayInputRequest(
                    tip=tip,
                    mode="single",
                    preset=default,
                    is_password=is_password,
                )
                result = gateway.request_input(request)
                return result.text.strip() if result is not None else default.strip()
            except InputProviderTimeoutError:
                PrettyOutput.auto_print("⚠ Input timed out, using default value\n")
                return default.strip()
            except InputProviderDisconnectedError:
                PrettyOutput.auto_print("⚠ WebSocket not connected, waiting for frontend to reconnect...\n")
                time.sleep(2)

    # Non-Gateway mode: use command-line input
    history_dir = get_data_dir()
    session: PromptSession[Any] = PromptSession(
        history=FileHistory(os.path.join(history_dir, "single_line_input_history"))
    )
    style = PromptStyle.from_dict(
        {"prompt": "ansicyan", "bottom-toolbar": "fg:#888888"}
    )
    prompt = FormattedText([("class:prompt", f"👤 > {tip}")])
    return str(
        session.prompt(prompt, default=default, style=style, is_password=is_password)
    ).strip()


def get_choice(tip: str, choices: List[str]) -> str:
    """
    Provide a scrollable selection list for the user to choose from.

    In CLI mode, prefer using fzf for fast fuzzy filtering (if fzf is available),
    otherwise fall back to numbering via single-line input.
    In Gateway mode, print the option list + single-line input.
    """
    if not choices:
        raise ValueError("Choices cannot be empty.")

    # Check if in Gateway mode
    gateway = None
    GatewayInputRequest = None
    try:
        from haijunbot.haijunbot_gateway.events import (
            GatewayInputRequest as _GatewayInputRequest,
        )
        from haijunbot.haijunbot_gateway.manager import get_current_gateway

        gateway = get_current_gateway()
        GatewayInputRequest = _GatewayInputRequest
    except Exception:
        gateway = None

    if gateway is not None and GatewayInputRequest is not None:
        # Gateway mode: print options list once and get selection via single-line input
        lines = [tip]
        for i, choice in enumerate(choices, 1):
            lines.append(f"  {i}. {choice}")
        PrettyOutput.auto_print("\n".join(lines))

        result = get_single_line_input("Please enter option number: ", default="1")
        try:
            index = int(result.strip()) - 1
            if 0 <= index < len(choices):
                return choices[index]
        except ValueError:
            pass
        # Invalid input returns first option as default
        return choices[0]

    # CLI mode: try fzf first
    try:
        from haijunbot.haijunbot_utils.fzf import fzf_select

        selected = fzf_select(choices, prompt=f"{tip} (type to filter, Ctrl+C to cancel): ")
        if selected is not None:
            return selected
        # fzf cancelled by user (Esc/Ctrl+C), return empty string directly
        return ""
    except (ImportError, Exception):
        pass  # fzf module unavailable or other error, fallback to single-line input

    # CLI mode: when fzf unavailable, use single-line index input
    lines = [tip]
    for i, choice in enumerate(choices, 1):
        lines.append(f"  {i}. {choice}")
    PrettyOutput.auto_print("\n".join(lines))

    result = get_single_line_input("Please enter option number: ", default="1")
    try:
        index = int(result.strip()) - 1
        if 0 <= index < len(choices):
            return choices[index]
    except ValueError:
        pass
    # Invalid input returns first option as default
    return choices[0]


class FileCompleter(Completer):
    """
    Custom file path completer with fuzzy matching.
    """

    def __init__(self) -> None:
        self.path_completer = PathCompleter()
        self.max_suggestions = 30
        self.min_score = 10
        self.replace_map = get_replace_map()
        # Caches for file lists to avoid repeated expensive scans
        self._git_files_cache: Optional[List[str]] = None
        self._all_files_cache: Optional[List[str]] = None
        self._max_walk_files = 10000
        # Cache for rules to avoid repeated loading
        self._rules_cache: Optional[List[Tuple[str, str]]] = None
        # Load completion usage stats
        self._usage_stats: Dict[str, int] = _load_completion_usage_stats()

    def _get_all_rule_completions(self) -> List[str]:
        """Unified interface for getting all rule completion items

        Returns:
            List[str]: List of rules in format "<rule:{rule_name}>"
        """
        all_rules = []
        try:
            from haijunbot.haijunbot_agent.rules_manager import RulesManager

            rules_manager = RulesManager(os.getcwd())
            available_rules = rules_manager.get_all_available_rule_names()

            # Add built-in rules
            if available_rules.get("builtin"):
                for rule_name in available_rules["builtin"]:
                    all_rules.append(f"<rule:{rule_name}>")

            # Add file rules
            if available_rules.get("files"):
                for rule_name in available_rules["files"]:
                    all_rules.append(f"<rule:{rule_name}>")

            # Add YAML rules
            if available_rules.get("yaml"):
                for rule_name in available_rules["yaml"]:
                    all_rules.append(f"<rule:{rule_name}>")
        except ImportError:
            # If import fails, use only built-in rules
            try:
                from haijunbot.haijunbot_agent.builtin_rules import list_builtin_rules

                for rule_name in list_builtin_rules():
                    all_rules.append(f"<rule:{rule_name}>")
            except ImportError:
                pass
        except Exception:
            # Silently handle any errors
            pass

        return all_rules

    def _get_all_rules(self) -> List[Tuple[str, str]]:
        """Get all available rules including built-in, file, and YAML rules

        Returns:
            List[Tuple[str, str]]: (rule_name, rule_description) list
        """
        if self._rules_cache is not None:
            return self._rules_cache

        all_rules = []

        try:
            # Import required modules
            from haijunbot.haijunbot_agent.rules_manager import RulesManager

            # Create RulesManager instance
            rules_manager = RulesManager(os.getcwd())

            # Get all available rules
            available_rules = rules_manager.get_all_available_rule_names()

            # Add built-in rules
            if available_rules.get("builtin"):
                for rule_name in available_rules["builtin"]:
                    all_rules.append((rule_name, f"📚 Built-in rule: {rule_name}"))

            # Add file rules
            if available_rules.get("files"):
                for rule_name in available_rules["files"]:
                    all_rules.append((rule_name, f"📄 File rule: {rule_name}"))

            # Add YAML rules
            if available_rules.get("yaml"):
                for rule_name in available_rules["yaml"]:
                    all_rules.append((rule_name, f"📝 YAML rule: {rule_name}"))

        except ImportError:
            # If import fails, use only built-in rules
            try:
                from haijunbot.haijunbot_agent.builtin_rules import list_builtin_rules

                for rule_name in list_builtin_rules():
                    all_rules.append((rule_name, f"📚 Built-in rule: {rule_name}"))
            except ImportError:
                pass
        except Exception:
            # Silently handle any errors
            pass

        self._rules_cache = all_rules
        return all_rules

    def get_completions(
        self, document: Document, complete_event: CompleteEvent
    ) -> Iterable[Completion]:
        text = document.text_before_cursor
        cursor_pos = document.cursor_position

        # Support both '@' (git files) and '#' (all files excluding .git)
        sym_positions = [(i, ch) for i, ch in enumerate(text) if ch in ("@", "#")]
        if not sym_positions:
            return
        current_pos = None
        current_sym = None
        for i, ch in sym_positions:
            if i < cursor_pos:
                current_pos = i
                current_sym = ch
        if current_pos is None:
            return

        text_after = text[current_pos + 1 : cursor_pos]
        if " " in text_after:
            return

        token = text_after.strip()
        replace_length = len(text_after) + 1

        all_completions = []
        all_completions.extend(
            [(ot(tag), self._get_description(tag)) for tag in self.replace_map.keys()]
        )
        all_completions.extend([(ot(cmd), desc) for cmd, desc in BUILTIN_COMMANDS])
        # Add all rules (built-in, file, YAML) to completion list
        rules = self._get_all_rules()
        for rule_name, rule_desc in rules:
            all_completions.append((f"<rule:{rule_name}>", rule_desc))

        # File path candidates
        try:
            additional_paths = _get_additional_dir_files(exclude_git=True)
            if current_sym == "@":
                if self._git_files_cache is None:
                    result = _subprocess.run(
                        ["git", "ls-files"],
                        stdout=_subprocess.PIPE,
                        stderr=_subprocess.PIPE,
                        text=False,
                    )
                    if result.returncode == 0:
                        self._git_files_cache = [
                            p
                            for p in decode_output(result.stdout).splitlines()
                            if p.strip()
                        ]
                    else:
                        self._git_files_cache = []
                paths = _merge_unique_paths(
                    self._git_files_cache or [], additional_paths
                )
            else:
                if self._all_files_cache is None:
                    files: List[str] = []
                    for root, dirs, fnames in _os.walk(".", followlinks=False):
                        # Explicitly include hidden directories (starting with .), but exclude .git, __pycache__, .pytest_cache, etc.
                        dirs[:] = [
                            d
                            for d in dirs
                            if d
                            not in {
                                ".git",
                                "__pycache__",
                                ".pytest_cache",
                                ".mypy_cache",
                                ".ruff_cache",
                                "node_modules",
                                "target",
                            }
                        ]
                        for name in fnames:
                            files.append(
                                _os.path.relpath(_os.path.join(root, name), ".")
                            )
                            if len(files) > self._max_walk_files:
                                break
                        if len(files) > self._max_walk_files:
                            break
                    self._all_files_cache = files
                paths = _merge_unique_paths(
                    self._all_files_cache or [], additional_paths
                )
            all_completions.extend([(path, "File") for path in paths])
        except Exception as e:
            save_exception(e, module="haijunbot_utils.input", function="get_completions")
            pass

        if token:
            # Check if token contains only punctuation/special characters
            # This prevents fuzzywuzzy processor from reducing it to empty string
            token_stripped = token.strip()
            if token_stripped and not any(c.isalnum() for c in token_stripped):
                # Token contains only punctuation/special chars, skip fuzzy matching
                # to avoid warning from fuzzywuzzy processor
                for t, desc in all_completions[: self.max_suggestions]:
                    yield Completion(
                        text=f"'{t}'",
                        start_position=-replace_length,
                        display=t,
                        display_meta=desc,
                    )
            else:
                scored_items = process.extract(
                    token,
                    [item[0] for item in all_completions],
                    limit=self.max_suggestions,
                )
                # Adjust scores based on usage stats
                scored_items_with_usage: List[Tuple[str, int, int]] = []
                for item_path, score in scored_items:
                    usage_count = self._usage_stats.get(item_path, 0)
                    # Add usage count as weight (usage_count * 5 to balance with fuzzy score)
                    final_score = score + (usage_count * 5)
                    scored_items_with_usage.append((item_path, final_score, score))

                # Sort by final score and filter by minimum score
                scored_items_with_usage.sort(key=lambda x: x[1], reverse=True)
                # Filter by minimum score and limit to max_suggestions
                filtered_items: List[Tuple[str, int, int]] = [
                    item for item in scored_items_with_usage if item[2] > self.min_score
                ][: self.max_suggestions]

                completion_map = {item[0]: item[1] for item in all_completions}
                for t, final_score, original_score in filtered_items:
                    display_text = (
                        f"{t} ({original_score}%)" if original_score < 100 else t
                    )
                    yield Completion(
                        text=f"'{t}'",
                        start_position=-replace_length,
                        display=display_text,
                        display_meta=completion_map.get(t, ""),
                    )
        else:
            for t, desc in all_completions[: self.max_suggestions]:
                yield Completion(
                    text=f"'{t}'",
                    start_position=-replace_length,
                    display=t,
                    display_meta=desc,
                )

    def _get_description(self, tag: str) -> str:
        if tag in self.replace_map:
            return (
                self.replace_map[tag].get("description", tag) + "(Append)"
                if "append" in self.replace_map[tag] and self.replace_map[tag]["append"]
                else "(Replace)"
            )
        return tag


def get_all_rules_formatted() -> List[str]:
    """
    Get formatted list of all available rules including built-in, file, and YAML rules.

    Returns:
        List[str]: Formatted rule list, each rule returned as "<rule:rule_name>"

    Exception handling:
        - Handle RulesManager import failure
        - Handle built-in rules import failure
        - Return empty list on any error instead of raising exception
    """
    all_rules = []
    try:
        try:
            from haijunbot.haijunbot_agent.rules_manager import RulesManager

            rules_manager = RulesManager(os.getcwd())
            available_rules = rules_manager.get_all_available_rule_names()

            # Add built-in rules
            if available_rules.get("builtin"):
                for rule_name in available_rules["builtin"]:
                    all_rules.append(f"<rule:{rule_name}>")

            # Add file rules
            if available_rules.get("files"):
                for rule_name in available_rules["files"]:
                    all_rules.append(f"<rule:{rule_name}>")

            # Add YAML rules
            if available_rules.get("yaml"):
                for rule_name in available_rules["yaml"]:
                    all_rules.append(f"<rule:{rule_name}>")
        except ImportError:
            # If RulesManager import fails, use only built-in rules
            try:
                from haijunbot.haijunbot_agent.builtin_rules import list_builtin_rules

                for rule_name in list_builtin_rules():
                    all_rules.append(f"<rule:{rule_name}>")
            except ImportError:
                pass
    except Exception:
        # Any exception returns empty list
        all_rules = []

    return all_rules


def _get_fzf_completion_items(specials: List[str], files: List[str]) -> List[str]:
    """
    Get full list of items needed for fzf completion.

    This function unifies handling of all item types needed for fzf completion including special symbols, built-in tags, rules, files, etc.,
    Eliminates duplicate logic in two fzf completion code locations.

    Parameters:
        specials: List of special symbols
        files: List of files

    Returns:
        List[str]: Merged full item list in specific order
    """
    items = []

    # Add special symbols (filter empty strings)
    items.extend([s for s in specials if isinstance(s, str) and s.strip()])

    # Add built-in tags
    try:
        from haijunbot.haijunbot_utils.config import get_replace_map
        from haijunbot.haijunbot_utils.tag import ot

        replace_map = get_replace_map()
        builtin_tags = [
            ot(tag)
            for tag in replace_map.keys()
            if isinstance(tag, str) and tag.strip()
        ]
        items.extend(builtin_tags)

        # Add built-in command tags
        builtin_commands = [ot(cmd) for cmd, _ in BUILTIN_COMMANDS]
        items.extend(builtin_commands)
    except Exception:
        # Skip if tag retrieval fails
        pass

    # Add rules
    try:
        builtin_rules = get_all_rules_formatted()
        items.extend(builtin_rules)
    except Exception:
        # Skip if rule retrieval fails
        pass

    # Add files
    items.extend(files)

    return items


# -+
# Common judgment helper (prioritizes current Agent)
# ---------------------
def _get_current_agent_for_input() -> Optional[Any]:
    try:
        import haijunbot.haijunbot_utils.globals as g

        current_name = g.get_current_agent_name()
        if current_name:
            return g.get_agent(current_name)
    except Exception as e:
        save_exception(
            e, module="haijunbot_utils.input", function="_get_current_agent_for_input"
        )
        pass
    return None


def _is_non_interactive_for_current_agent() -> bool:
    try:
        from haijunbot.haijunbot_utils.config import is_non_interactive

        ag = _get_current_agent_for_input()
        try:
            return (
                bool(getattr(ag, "non_interactive", False))
                if ag
                else bool(is_non_interactive())
            )
        except Exception:
            return bool(is_non_interactive())
    except Exception:
        return False


def _is_auto_complete_for_current_agent() -> bool:
    try:
        ag = _get_current_agent_for_input()
        if ag is not None and hasattr(ag, "auto_complete"):
            try:
                return bool(getattr(ag, "auto_complete", False))
            except Exception as e:
                save_exception(
                    e,
                    module="haijunbot_utils.input",
                    function="_is_auto_complete_for_current_agent",
                )
                pass
        return False
    except Exception:
        return False


def _get_agent_hint() -> str:
    """Get prompt info for current Agent (list of available agents)."""
    try:
        ag = _get_current_agent_for_input()
        ohs = getattr(ag, "output_handler", [])
        available_agents: List[str] = []
        for oh in ohs or []:
            cfgs = getattr(oh, "agents_config", None)
            if isinstance(cfgs, list):
                for c in cfgs:
                    try:
                        name = c.get("name")
                    except Exception:
                        name = None
                    if isinstance(name, str) and name.strip():
                        available_agents.append(name.strip())
        if available_agents:
            # Deduplicate while preserving order
            seen = set()
            ordered = []
            for n in available_agents:
                if n not in seen:
                    seen.add(n)
                    ordered.append(n)
            return (
                "\nCurrently available agents: "
                + ", ".join(ordered)
                + f"\nTo delegate task to another agent, use {ot('SEND_MESSAGE')} block."
            )
    except Exception as e:
        save_exception(e, module="haijunbot_utils.input", function="_get_agent_hint")
        pass
    return ""


def _get_non_interactive_response(auto_complete: bool) -> str:
    """
    Get response text in non-interactive mode."""
    hint = _get_agent_hint()
    if auto_complete:
        base_msg = (
            "No tool calls detected in this turn. Currently in non-interactive mode; you must make all decisions yourself, and if you cannot decide, complete the task. Output"
            + ot("!!!COMPLETE!!!")
        )
        return base_msg + hint

    else:
        return (
            "No tool calls detected in this turn. Currently in non-interactive mode; you must make all decisions yourself" + hint
        )


def user_confirm(tip: str, default: bool = True) -> bool:
    """Prompt user to confirm yes/no (prioritize current Agent to determine non-interactive mode)"""
    try:
        if _is_non_interactive_for_current_agent():
            return default

        # Get current agent name and add to prompt prefix
        agent_name = ""
        try:
            ag = _get_current_agent_for_input()
            if ag is not None:
                name = getattr(ag, "name", None)
                if name:
                    agent_name = f"[{name}] "
        except Exception as e:
            save_exception(e, module="haijunbot_utils.input", function="user_confirm")
            pass

        # Check if in Gateway mode
        gateway = None
        GatewayConfirmRequest = None
        try:
            from haijunbot.haijunbot_gateway.events import (
                GatewayConfirmRequest as _GatewayConfirmRequest,
            )
            from haijunbot.haijunbot_gateway.manager import get_current_gateway

            gateway = get_current_gateway()
            GatewayConfirmRequest = _GatewayConfirmRequest
        except Exception:
            gateway = None

        suffix = "[Y/n]" if default else "[y/N]"
        message = f"{agent_name}{tip} {suffix}"

        if gateway is not None and GatewayConfirmRequest is not None:
            # Gateway mode: send confirmation request to frontend; wait for reconnection if disconnected
            import time

            while True:
                try:
                    request = GatewayConfirmRequest(message=message, default=default)
                    result = gateway.request_confirm(request)
                    return result.confirmed if result is not None else default
                except InputProviderTimeoutError:
                    PrettyOutput.auto_print("⚠ Confirmation timeout, using default value\n")
                    return default
                except InputProviderDisconnectedError:
                    PrettyOutput.auto_print("⚠ WebSocket not connected, waiting for frontend reconnection...\n")
                    time.sleep(2)

        # CLI mode: local input
        ret = get_single_line_input(f"{agent_name}{tip} {suffix}: ")
        return default if ret == "" else ret.lower() == "y"
    except KeyboardInterrupt:
        return False


def _show_history_and_copy() -> None:
    """
    Display message history and handle copying to clipboard.
    This function uses standard I/O and can be safely called outside prompt sessions.
    """

    history = get_message_history()
    if not history:
        PrettyOutput.auto_print("ℹ️ No messages to copy")
        return

    # To avoid PrettyOutput adding borders per line in loop, concatenate first then print together
    lines = []
    lines.append("\n" + "=" * 20 + " 📜 Message History " + "=" * 20)
    for i, msg in enumerate(history):
        cleaned_msg = msg.replace("\n", r"\n")
        display_msg = (
            (cleaned_msg[:70] + "...") if len(cleaned_msg) > 70 else cleaned_msg
        )
        lines.append(f"  {i + 1}: {display_msg.strip()}")
        lines.append("=" * 58 + "\n")
    PrettyOutput.auto_print("\n".join(lines))

    while True:
        try:
            prompt_text = f"{Fore.CYAN}Enter item number to copy (or 'c' to cancel, Enter to select last): {ColoramaStyle.RESET_ALL}"
            choice_str = input(prompt_text)

            if not choice_str:  # User pressed Enter
                if not history:
                    PrettyOutput.auto_print("ℹ️ No history available to select.")
                    break
                choice = len(history) - 1
            elif choice_str.lower() == "c":
                PrettyOutput.auto_print("ℹ️ Cancelled")
                break
            else:
                choice = int(choice_str) - 1

            if 0 <= choice < len(history):
                selected_msg = history[choice]
                copy_to_clipboard(selected_msg)
                PrettyOutput.auto_print(f"✅ Copied message: {selected_msg[:70]}...")
                break
            else:
                PrettyOutput.auto_print("⚠️ Invalid number, please retry.")
        except ValueError:
            PrettyOutput.auto_print("⚠️ Invalid input, please enter a number.")
        except (KeyboardInterrupt, EOFError):
            PrettyOutput.auto_print("ℹ️ Operation cancelled")
            break


def _get_multiline_input_internal(
    tip: str,
    preset: Optional[str] = None,
    preset_cursor: Optional[int] = None,
    provider: Optional["CLIInputProvider"] = None,
) -> str:
    """
    Internal function to get multiline input using prompt_toolkit.
    Returns a sentinel value if Ctrl+O is pressed.
    """
    bindings = KeyBindings()

    # Show a one-time hint on the first Enter press in this invocation (disabled; using inlay toolbar instead)
    first_enter_hint_shown = True

    @bindings.add("enter")
    def _(event: KeyPressEvent) -> None:
        nonlocal first_enter_hint_shown
        if not first_enter_hint_shown and not _multiline_hint_already_shown():
            first_enter_hint_shown = True

            # Generate shortcut key display text
            submit_keys = get_submit_keys()
            submit_keys_display = " or ".join(
                [k.replace("c-", "Ctrl+").upper() for k in submit_keys]
            )

            def _show_notice() -> None:
                PrettyOutput.auto_print(
                    f"ℹ️ Tip: Multi-line input supported. Use {submit_keys_display} to confirm; Enter is for line breaks only."
                )
                try:
                    input("Press Enter to continue...")
                except Exception as e:
                    save_exception(
                        e, module="haijunbot_utils.input", function="_show_notice"
                    )
                    pass
                # Persist the hint so it won't be shown again in future runs
                try:
                    _mark_multiline_hint_shown()
                except Exception as e:
                    save_exception(
                        e, module="haijunbot_utils.input", function="_show_notice"
                    )
                    pass

            run_in_terminal(_show_notice)
            return

        if event.current_buffer.complete_state:
            completion = event.current_buffer.complete_state.current_completion
            if completion:
                event.current_buffer.apply_completion(completion)
                # Track completion usage when user selects an item
                if hasattr(completion, "text") and completion.text:
                    # Extract item from completion text (remove quotes)
                    item = completion.text.strip("'\"")
                    # Track all completions (files, commands, etc.)
                    if item:
                        _update_completion_usage(item)
            else:
                event.current_buffer.insert_text("\n")
        else:
            event.current_buffer.insert_text("\n")

    # Get submit shortcut key list from config
    submit_keys = get_submit_keys()
    for key in submit_keys:

        @bindings.add(key, filter=has_focus(DEFAULT_BUFFER))
        def _(event: KeyPressEvent) -> None:
            event.current_buffer.validate_and_handle()

    @bindings.add("c-o", filter=has_focus(DEFAULT_BUFFER))
    def _(event: KeyPressEvent) -> None:
        """Handle Ctrl+O by exiting the prompt and returning the sentinel value."""
        event.app.exit(result=CTRL_O_SENTINEL)

    @bindings.add("c-x", filter=has_focus(DEFAULT_BUFFER))
    def _(event: KeyPressEvent) -> None:
        """Handle Ctrl+X by exiting the prompt and requesting program exit."""
        event.app.exit(result=CTRL_X_SENTINEL)

    def _handle_shell_cmd(event: KeyPressEvent) -> None:
        """Handle shell command trigger (called by Ctrl+T and Alt+T).

        This binding works globally (without focus filter) so it can be triggered
        even when LLM is outputting or after interrupting output with Ctrl+C.
        """
        # Exit the prompt with a sentinel; the outer get_multiline_input loop
        # will open an interactive shell terminal and continue prompting.
        event.app.exit(result=CTRL_T_SENTINEL)

    @bindings.add("c-t", eager=True)
    def _(event: KeyPressEvent) -> None:
        """Handle Ctrl+T to trigger shell command (CLI mode)."""
        _handle_shell_cmd(event)

    @bindings.add("escape", "t", eager=True)
    def _(event: KeyPressEvent) -> None:
        """Handle Alt+T to trigger shell command (CLI/Web mode)."""
        _handle_shell_cmd(event)

    @bindings.add("@", filter=has_focus(DEFAULT_BUFFER), eager=True)
    def _(event: KeyPressEvent) -> None:
        """
        Use @ to trigger fzf (if fzf exists); otherwise just insert @ to enable built-in completion
        Logic:
        - If fzf exists on system, insert '@' first, then request outer layer to run fzf and replace/insert after return
        - If fzf does not exist or exception occurs, directly insert '@' and trigger completion
        """
        try:
            buf = event.current_buffer
            if _shutil.which("fzf") is None:
                buf.insert_text("@")
                # Manually trigger completion to show rule and other completion options
                buf.start_completion(select_first=False)
                return
            # Insert '@', so outer layer can replace fragment based on last '@' fragment replacement
            buf.insert_text("@")
            doc = buf.document
            text = doc.text
            cursor = doc.cursor_position
            payload = (
                f"{cursor}:{base64.b64encode(text.encode('utf-8')).decode('ascii')}"
            )
            event.app.exit(result=FZF_REQUEST_SENTINEL_PREFIX + payload)
            return
        except Exception:
            try:
                buf = event.current_buffer
                buf.insert_text("@")
                # Try to trigger completion even if exception occurs
                buf.start_completion(select_first=False)
            except Exception as e:
                save_exception(e, module="haijunbot_utils.input", function="_")
                pass

    @bindings.add("#", filter=has_focus(DEFAULT_BUFFER), eager=True)
    def _(event: KeyPressEvent) -> None:
        """
        Use # to trigger fzf (if fzf exists) in "full file mode" (exclude .git); otherwise just insert # to enable built-in completion
        """
        try:
            buf = event.current_buffer
            if _shutil.which("fzf") is None:
                buf.insert_text("#")
                # Manually trigger completion to show rule and other completion options
                buf.start_completion(select_first=False)
                return
            # Insert '#'
            buf.insert_text("#")
            doc = buf.document
            text = doc.text
            cursor = doc.cursor_position
            payload = (
                f"{cursor}:{base64.b64encode(text.encode('utf-8')).decode('ascii')}"
            )
            event.app.exit(result=FZF_REQUEST_ALL_SENTINEL_PREFIX + payload)
            return
        except Exception:
            try:
                buf = event.current_buffer
                buf.insert_text("#")
                # Try to trigger completion even if exception occurs
                buf.start_completion(select_first=False)
            except Exception as e:
                save_exception(e, module="haijunbot_utils.input", function="_")
                pass

    style = PromptStyle.from_dict(
        {
            "prompt": "ansibrightmagenta bold",
            "bottom-toolbar": "bg:#4b145b #ffd6ff bold",
            "bt.tip": "bold fg:#ff5f87",
            "bt.sep": "fg:#ffb3de",
            "bt.key": "bg:#d7005f #ffffff bold",
            "bt.label": "fg:#ffd6ff",
            "placeholder": "italic fg:#888888",
        }
    )

    # Get submit shortcut key display text
    submit_keys = get_submit_keys()
    # Convert shortcut keys to display format (e.g., "c-j" -> "Ctrl+J")
    submit_keys_display = "/".join(
        [k.replace("c-", "Ctrl+").upper() for k in submit_keys]
    )

    def _bottom_toolbar() -> Any:
        return FormattedText(
            [
                ("class:bt.label", "Shortcuts: "),
                ("class:bt.key", "@"),
                ("class:bt.label", " File Complete "),
                ("class:bt.sep", " • "),
                ("class:bt.key", submit_keys_display),
                ("class:bt.label", " Submit "),
                ("class:bt.sep", " • "),
                ("class:bt.key", "Ctrl+O"),
                ("class:bt.label", " Copy History "),
                ("class:bt.sep", " • "),
                ("class:bt.key", "Alt+T"),
                ("class:bt.label", " Terminal (!SHELL) "),
                ("class:bt.sep", " • "),
                ("class:bt.key", "Ctrl+X"),
                ("class:bt.label", " Exit Program "),
                ("class:bt.sep", " • "),
                ("class:bt.key", "Ctrl+C"),
                ("class:bt.label", " Cancel "),
            ]
        )

    history_dir = get_data_dir()
    session: PromptSession[Any] = PromptSession(
        history=FileHistory(os.path.join(history_dir, "multiline_input_history")),
        completer=FileCompleter(),
        key_bindings=bindings,
        complete_while_typing=True,
        multiline=True,
        vi_mode=False,
        mouse_support=False,
    )

    # Tip is shown in placeholder; avoid extra print
    prompt = FormattedText([("class:prompt", "👤 > ")])

    def _pre_run() -> None:
        try:
            from prompt_toolkit.application.current import get_app as _ga

            app = _ga()
            buf = app.current_buffer
            if preset is not None and preset_cursor is not None:
                cp = max(0, min(len(buf.text), preset_cursor))
                buf.cursor_position = cp
        except Exception as e:
            save_exception(e, module="haijunbot_utils.input", function="_pre_run")
            pass

    try:
        result = session.prompt(
            prompt,
            style=style,
            pre_run=_pre_run,
            bottom_toolbar=_bottom_toolbar,
            placeholder=FormattedText([("class:placeholder", tip)]),
            default=(preset or ""),
        )
        return str(result).strip() if result else ""
    except (KeyboardInterrupt, EOFError):
        # Check global buffer; return injected content if present
        if provider is not None:
            injected = provider._check_injected_buffer()
            if injected is not None:
                return injected
        return CTRL_C_SENTINEL


def get_multiline_input(tip: str, print_on_empty: bool = True) -> str:
    """
    Get multi-line input with enhanced completion and confirmation.
    This function handles control flow to allow history copying without breaking terminal state.

    Parameters:
        tip: Prompt text to display in bottom toolbar
        print_on_empty: Whether to print a hint when the input is empty, such as "Cancelled".
    """
    # Submit key handling
    submit_keys = get_submit_keys()
    submit_keys_display = "/".join(
        [k.replace("c-", "Ctrl+").upper() for k in submit_keys]
    )

    preset: Optional[str] = None
    preset_cursor: Optional[int] = None
    while True:
        # Accurately determine non-interactive mode and auto-completion based on current Agent to avoid interference between agents
        if _is_non_interactive_for_current_agent():
            return _get_non_interactive_response(_is_auto_complete_for_current_agent())

        def _get_input_via_provider() -> str:
            provider = get_current_input_provider()
            return provider.get_multiline_input(
                tip, preset=preset, preset_cursor=preset_cursor
            )

        gateway = None
        GatewayInputRequest = None
        try:
            from haijunbot.haijunbot_gateway.events import (
                GatewayInputRequest as _GatewayInputRequest,
            )
            from haijunbot.haijunbot_gateway.manager import get_current_gateway

            gateway = get_current_gateway()
            GatewayInputRequest = _GatewayInputRequest
        except Exception:
            gateway = None

        try:
            if gateway is not None and GatewayInputRequest is not None:
                request = GatewayInputRequest(
                    tip=tip,
                    mode="multi",
                    preset=preset,
                    preset_cursor=preset_cursor,
                )
                result = gateway.request_input(request)
                user_input = result.text if result is not None else ""
            else:
                user_input = _get_input_via_provider()
        except InputProviderTimeoutError:
            PrettyOutput.auto_print("⚠️  Input timed out, cancelled")
            return ""
        except InputProviderDisconnectedError:
            # Web Gateway mode: do not exit on disconnection, continue waiting for reconnection
            if gateway is not None:
                continue
            # CLI mode: keep as-is, return empty string to trigger exit
            PrettyOutput.auto_print("⚠️  Input disconnected, cancelled")
            return ""
        except Exception:
            user_input = _get_input_via_provider()

        if user_input == CTRL_O_SENTINEL:
            _show_history_and_copy()
            tip = f" (or {submit_keys_display} to confirm):"
            continue
        if user_input == CTRL_X_SENTINEL:
            PrettyOutput.auto_print("🛑  Exit Program...")
            raise SystemExit(0)
        elif isinstance(user_input, str) and user_input.startswith(
            FZF_REQUEST_SENTINEL_PREFIX
        ):
            # Handle fzf request outside the prompt, then prefill new text.
            cursor, text = _parse_fzf_payload(user_input, FZF_REQUEST_SENTINEL_PREFIX)
            if cursor is None or text is None:
                # Malformed payload; just continue without change.
                preset = None
                tip = "FZF prefill failed, continue typing:"
                continue

            # Run fzf to get a file selection synchronously (outside prompt)
            files = _get_files_for_fzf(use_git=True)
            selected_path = _run_fzf_for_selection(files, "Files> ")

            # Compute new text based on selection (or keep original if none)
            if selected_path:
                preset, preset_cursor = _insert_file_path(
                    text, cursor, selected_path, "@"
                )
                tip = f" (or {submit_keys_display}):"
            else:
                # No selection; keep original text and cursor
                preset = text
                preset_cursor = cursor
                tip = " (or cancel):"
            _clear_previous_prompt(text)
            continue
        elif isinstance(user_input, str) and user_input.startswith(
            FZF_REQUEST_ALL_SENTINEL_PREFIX
        ):
            # Handle fzf request (all-files mode, excluding .git) outside the prompt, then prefill new text.
            cursor, text = _parse_fzf_payload(
                user_input, FZF_REQUEST_ALL_SENTINEL_PREFIX
            )
            if cursor is None or text is None:
                # Malformed payload; just continue without change.
                preset = None
                tip = "FZF prefill failed, continue typing:"
                continue

            # Run fzf to get a file selection synchronously (outside prompt) with all files (exclude .git)
            files = _get_all_files(exclude_git=True)
            selected_path = _run_fzf_for_selection(files, "Files(all)> ")

            # Compute new text based on selection (or keep original if none)
            if selected_path:
                preset, preset_cursor = _insert_file_path(
                    text, cursor, selected_path, "#"
                )
                tip = f" (or {submit_keys_display}):"
            else:
                # No selection; keep original text and cursor
                preset = text
                preset_cursor = cursor
                tip = " (or cancel):"
            _clear_previous_prompt(text)
            continue
        elif isinstance(user_input, str) and user_input.startswith(
            FZF_INSERT_SENTINEL_PREFIX
        ):
            # Extract new text from sentinel payload as prefill for next prompt
            preset = user_input[len(FZF_INSERT_SENTINEL_PREFIX) :]
            preset_cursor = len(preset)

            # Clear previous input line (multi-line safe), avoid over-clearing; conservatively estimate by prompt lines
            try:
                rows_total = _calc_prompt_rows(preset)
                for _ in range(rows_total):
                    sys.stdout.write("\x1b[1A")
                    sys.stdout.write("\x1b[2K\r")
                sys.stdout.flush()
            except Exception as e:
                save_exception(
                    e, module="haijunbot_utils.input", function="_get_input_via_provider"
                )
                pass
            tip = f" (or {submit_keys_display}):"
            continue
        else:
            if user_input == CTRL_C_SENTINEL:
                # Ctrl+C pressed, allow exit and return empty string
                return ""
            elif user_input == CTRL_T_SENTINEL:
                # Alt+T/Ctrl+T pressed: open an interactive shell terminal,
                # then continue prompting for user input.
                execute_shell_in_terminal(_get_current_agent_for_input())
                continue
            elif not user_input:
                # Empty submission, require user to input something
                continue
            else:
                return user_input
