# -*- coding: utf-8 -*-
"""Tmux auto-start wrapper module

Detects whether tmux is installed on the system; if not running inside a tmux environment, automatically creates a tmux session and re-executes the command.
"""

import getpass
import os
import shlex
import shutil
import subprocess
import sys
import uuid
from typing import List, Optional

from haijunbot.haijunbot_utils.output import PrettyOutput


def _get_username() -> str:
    """Get the current username.

    Prefer getpass.getuser(), falling back to the USER environment variable,
    and finally returning 'unknown' as a fallback.

    Returns:
        str: username
    """
    try:
        return getpass.getuser()
    except Exception:
        return os.environ.get("USER", "unknown")


def _sanitize_username(username: str) -> str:
    """Clean special characters from the username to ensure the generated tmux session name is valid.

    Args:
        username: the original username

    Returns:
        str: the cleaned username
    """
    # Replace characters that may make the tmux session name invalid with underscores
    # tmux session names cannot contain certain special characters, such as @, +, ., etc.
    import re

    # Use a regular expression to replace all characters that are not alphanumeric or hyphens with underscores
    sanitized = re.sub(r"[^a-zA-Z0-9_-]", "_", username)
    # Ensure it does not start or end with a hyphen or underscore
    sanitized = sanitized.strip("-_")
    # If empty after cleaning, use 'unknown' as the default value
    if not sanitized:
        sanitized = "unknown"
    return sanitized


def _generate_session_name() -> str:
    """Generate a tmux session name prefixed with the username.

    Unified format: {username}-haijunbot-{uuid}
    Use a UUID to ensure uniqueness and support multi-user environments.

    Returns:
        str: the generated session name
    """
    username = _get_username()
    sanitized_username = _sanitize_username(username)
    unique_suffix = uuid.uuid4().hex[:8]
    return f"{sanitized_username}-haijunbot-{unique_suffix}"


def dispatch_to_tmux_window(
    task_arg: Optional[str],
    argv: list[str],
    window_name: str = "haijunbot-dispatch",
    stay_in_session_after_exit: bool = True,
    shell_fallback: bool = True,
) -> bool:
    """Dispatch a task to a new tmux pane for execution.

    Args:
        task_arg: task content (deprecated, kept for compatibility)
        argv: current command-line arguments (need to filter out --dispatch)
        window_name: window name prefix (deprecated, kept for compatibility)
        stay_in_session_after_exit: whether to keep the session active after the command finishes (True means start a shell to keep the session, False means exit directly)
        shell_fallback: whether to start a shell as a fallback after the command finishes (True means start a shell, False means do not start a shell and use the process as the entry point)

    Returns:
        bool: whether the dispatch succeeded (True means success, False means failure)

    Note:
        In a tmux environment, create a new pane directly in the current window.
        If not in a tmux environment, look for a tmux session created by haijunbot
        and create a pane in it as a fallback.
        Use horizontal split (split-window -h) to create a new pane, suitable for code tasks.
    """
    # Check whether tmux is enabled in the config
    # If launched by hcad/hjbd, ignore the enable_tmux config
    if os.environ.get("HAIJUNBOT_DISPATCHER_CALL") != "1":
        from haijunbot.haijunbot_utils.config import GLOBAL_CONFIG_DATA

        if not GLOBAL_CONFIG_DATA.get("enable_tmux", False):
            return False

    # Check whether tmux is installed
    tmux_path = shutil.which("tmux")
    if tmux_path is None:
        return False

    # Check whether already running in a tmux environment
    if "TMUX" not in os.environ:
        # Not in tmux; try to find a session created by haijunbot as a fallback
        return _dispatch_to_existing_haijunbot_session(
            task_arg, argv, stay_in_session_after_exit, shell_fallback
        )

    # Generate a window name (using the first 20 characters of the task content)
    if task_arg and str(task_arg).strip():
        # Clean the task content, removing newlines and special characters
        clean_task = str(task_arg).strip()[:20].replace("\n", " ").replace("\r", " ")
        window_name = f"{window_name}-{clean_task}"

    # Filter out the --dispatch/-d argument to avoid recursive dispatching
    # Since --dispatch/-d is a boolean argument, it usually carries no value
    # But for robustness, handle all possible formats
    filtered_argv = []
    skip_next = False
    for i, arg in enumerate(argv):
        if skip_next:
            skip_next = False
            continue
        if arg == "--dispatch" or arg == "-d":
            # Case 1: --dispatch/-d (no value), skip directly
            continue
        elif arg.startswith("--dispatch=") or arg.startswith("-d="):
            # Case 2: --dispatch=value/-d=value, skip the whole argument
            continue
        else:
            # Keep other arguments
            filtered_argv.append(arg)

    # Get the current window identifier for subsequent layout switching
    # tmux select-layout supports a target argument in the session_name:window_index format
    current_window = None
    try:
        result = subprocess.run(
            ["tmux", "display-message", "-p", "#{session_name}:#{window_index}"],
            capture_output=True,
            text=True,
            check=True,
        )
        current_window = result.stdout.strip()
        # Validate the format (should contain a colon separator)
        if not current_window or ":" not in current_window:
            PrettyOutput.auto_print(
                f"⚠️ Invalid window format: '{current_window}'",
                timestamp=None,
            )
            current_window = None
    except subprocess.CalledProcessError as e:
        PrettyOutput.auto_print(
            f"⚠️ Failed to get current window: {e}",
            timestamp=None,
        )

    # Build the tmux split-window command (create a new pane in the current window)
    # split-window -h "<command>" - horizontal split (left-right layout)
    executable = sys.executable
    # Use shlex.quote() to safely escape each argument to prevent shell injection
    quoted_args = [shlex.quote(arg) for arg in filtered_argv]
    # Get the user's default shell
    user_shell = os.environ.get("SHELL", "/bin/sh")
    # First change to the current working directory, then execute the command
    cwd = os.getcwd()
    command = f"cd {shlex.quote(cwd)} && {executable} {' '.join(quoted_args)}"
    # If the session must stay active and shell fallback is allowed, start a shell
    if stay_in_session_after_exit and shell_fallback:
        command += f'; exec "{user_shell}"'

    tmux_args = [
        "tmux",
        "split-window",
        "-h",  # horizontal split (left-right layout), suitable for code tasks
        command,
    ]

    # Execute the tmux command
    try:
        subprocess.run(tmux_args, check=True)
        return True
    except subprocess.CalledProcessError as e:
        PrettyOutput.auto_print(
            f"⚠️ Failed to dispatch to tmux window: {e}",
            timestamp=None,
        )
        return False


def check_and_launch_tmux(
    stay_in_session_after_exit: bool = True,
    shell_fallback: bool = True,
    config_file: Optional[str] = None,
) -> None:
    """Detect tmux and start a tmux session when needed.

    Args:
        stay_in_session_after_exit: whether to keep the session active after the command finishes (True means start a shell to keep the session, False means exit directly)
        shell_fallback: whether to start a shell as a fallback after the command finishes (True means start a shell, False means do not start a shell and use the process as the entry point)
        config_file: config file path; if provided, load the config first

    Note:
        This function uses subprocess.execvp to replace the current process; if successful, it will not return.
        Session names uniformly use the {username}-haijunbot-{uuid} format.
    """
    # Check whether tmux is enabled in the config
    # Use a module reference instead of a direct import to ensure the latest GLOBAL_CONFIG_DATA
    import haijunbot.haijunbot_utils.config as config_module

    # If the config has not been loaded yet, try to load it
    if not config_module.GLOBAL_CONFIG_DATA:
        try:
            from haijunbot.haijunbot_utils.utils import load_config as _load_config
            import haijunbot.haijunbot_utils.utils as utils_module

            # If config_file is provided, temporarily set the global config file name
            if config_file is not None:
                original_config_file = getattr(utils_module, "g_config_file", None)
                utils_module.g_config_file = config_file
                try:
                    _load_config()
                finally:
                    # Restore the original config file name
                    if original_config_file is not None:
                        utils_module.g_config_file = original_config_file
                    else:
                        utils_module.g_config_file = None
            else:
                # If config_file is not provided, load using the default path
                _load_config()
        except Exception:
            # If loading fails, continue execution using default values
            pass

    # Check the enable_tmux config (use a module reference to ensure the latest value)
    # If launched by hcad/hjbd, ignore the enable_tmux config
    if os.environ.get("HAIJUNBOT_DISPATCHER_CALL") != "1":
        enable_tmux = config_module.GLOBAL_CONFIG_DATA.get("enable_tmux", False)
        if not enable_tmux:
            return

    # Check whether tmux is installed
    tmux_path = shutil.which("tmux")
    if tmux_path is None:
        # tmux is not installed; continue normally
        return

    # Check whether already running in a tmux environment
    # tmux sets the TMUX environment variable
    if "TMUX" in os.environ:
        # Already in tmux; continue normally
        return

    # tmux is installed and we are not in tmux; prioritize finding an existing session
    existing_session = find_or_create_haijunbot_session(force_create=False)

    # If an existing session is found, create a panel in the current window of that session
    if existing_session:
        PrettyOutput.auto_print(
            f"ℹ️ Found existing session: {existing_session}, creating panel in the current window...",
            timestamp=None,
        )

        # Get the current executable path and arguments
        executable = sys.executable
        argv = sys.argv

        # Get the user's default shell
        user_shell = os.environ.get("SHELL", "/bin/sh")

        # Build the command
        quoted_args = [shlex.quote(arg) for arg in argv]
        command = f"{executable} {' '.join(quoted_args)}"
    # If the session must stay active and shell fallback is allowed, start a shell
        if stay_in_session_after_exit and shell_fallback:
            command += f'; exec "{user_shell}"'

        # Get the current window of the session
        current_window = get_session_current_window(existing_session)
        if not current_window:
            PrettyOutput.auto_print(
                f"⚠️ Cannot get the current window of session '{existing_session}', creating a new window...",
                timestamp=None,
            )
            # Fall back to creating a new window (original logic)
            try:
                result = subprocess.run(
                    [
                        "tmux",
                        "new-window",
                        "-F",
                        "#{window_index}",
                        "-t",
                        existing_session,
                        command,
                    ],
                    capture_output=True,
                    text=True,
                    check=True,
                )
                new_window_index = result.stdout.strip()
            except subprocess.CalledProcessError as e:
                PrettyOutput.auto_print(
                    f"⚠️ Failed to create new window in tmux session '{existing_session}': {e}",
                    timestamp=None,
                )
                return
        else:
            # Create a panel in the current window
            pane_id = create_panel(
                session_name=existing_session,
                window_id=current_window,
                initial_command=command,
                split_direction="h",
                stay_in_session_after_exit=stay_in_session_after_exit,
                shell_fallback=shell_fallback,
            )
            if not pane_id:
                PrettyOutput.auto_print(
                    f"⚠️ Failed to create panel in window '{current_window}', creating a new window...",
                    timestamp=None,
                )
                # Fall back to creating a new window (original logic)
                try:
                    result = subprocess.run(
                        [
                            "tmux",
                            "new-window",
                            "-F",
                            "#{window_index}",
                            "-t",
                            existing_session,
                            command,
                        ],
                        capture_output=True,
                        text=True,
                        check=True,
                    )
                    new_window_index = result.stdout.strip()
                except subprocess.CalledProcessError as e:
                    PrettyOutput.auto_print(
                        f"⚠️ Failed to create new window in tmux session '{existing_session}': {e}",
                        timestamp=None,
                    )
                    return
            else:
                # Panel created successfully; attach directly to the current window
                new_window_index = current_window

        # Attach to the session (using the current window)
        attach_target = (
            f"{existing_session}:{new_window_index}"
            if new_window_index
            else existing_session
        )
        tmux_args = [
            "tmux",
            "attach",
            "-t",
            attach_target,
        ]
        try:
            os.execvp("tmux", tmux_args)
        except OSError as e:
            PrettyOutput.auto_print(
                f"⚠️ Failed to attach to tmux session '{existing_session}': {e}",
                timestamp=None,
            )
            return

    # No existing session found; create a new session
    # Add a random suffix to the session name to avoid conflicts
    session_name = _generate_session_name()
    # Build the tmux command: new-session -s <session_name> -- <command>
    # -s: specify the session name
    # --: the arguments that follow are the command to execute

    # Get the current executable path and arguments
    executable = sys.executable
    argv = sys.argv

    # Get the user's default shell
    user_shell = os.environ.get("SHELL", "/bin/sh")

    # Build the tmux command arguments
    # Refer to the implementation of dispatch_to_tmux_window and use shlex.quote to safely escape arguments
    quoted_args = [shlex.quote(arg) for arg in argv]
    command = f"{executable} {' '.join(quoted_args)}"
    # If the session must stay active and shell fallback is allowed, start a shell
    if stay_in_session_after_exit and shell_fallback:
        command += f'; exec "{user_shell}"'
    tmux_args = [
        "tmux",
        "new-session",
        "-s",
        session_name,
        command,
    ]

    # Replace the current process with tmux
    # execvp replaces the current process and does not return
    try:
        os.execvp("tmux", tmux_args)
    except OSError as e:
        # If execution fails, print a warning and continue
        PrettyOutput.auto_print(
            f"⚠️ Failed to launch tmux: {e}",
            timestamp=None,
        )
        return


def _find_haijunbot_session() -> Optional[str]:
    """Find a haijunbot tmux session.

    Returns:
        Optional[str]: the found session name, or None if not found

    Note:
        Only find "haijunbot" sessions with a username prefix.
        Format: {username}-haijunbot-{uuid}
    """
    try:
        result = subprocess.run(
            ["tmux", "list-sessions"],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
        # Get the username to build the prefix
        username = _get_username()
        sanitized_username = _sanitize_username(username)
        # Parse the session name: format is "session-name: windows (created ...)"
        for line in result.stdout.strip().split("\n"):
            if line.strip():
                # Extract the session name (the part before the colon)
                session_name = line.split(":")[0].strip()
                # Match sessions with a username prefix: {username}-haijunbot-{uuid}
                expected_prefix = f"{sanitized_username}-haijunbot-"
                if session_name.startswith(expected_prefix):
                    # Exact prefix match: check whether the part after removing the prefix is a number or UUID
                    suffix = session_name[len(expected_prefix) :]
                    if suffix and (
                        suffix[0].isdigit() or suffix[0] in "abcdef0123456789"
                    ):
                        # Match succeeded: the suffix starts with a digit or a UUID character
                        # Verify the session is actually usable to avoid returning sessions that exited abnormally
                        if has_session(session_name):
                            return session_name
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        # Normal case: do not print a warning when there are no active tmux sessions
        pass
    except Exception as e:
        # Keep warnings for genuine unexpected errors
        PrettyOutput.auto_print(
            f"⚠️ Unexpected error while listing sessions: {e}",
            timestamp=None,
        )
    return None


def list_session_windows(session_name: str) -> List[str]:
    """Get the list of windows for the specified tmux session.

    Args:
        session_name: tmux session name

    Returns:
        List[str]: list of windows, formatted as ["index: name", ...] (e.g., ["1: bash", "2: editor"])

    Note:
        If the session does not exist or the command fails, return an empty list.
        The window list is ordered by index.
    """
    try:
        result = subprocess.run(
            [
                "tmux",
                "list-windows",
                "-t",
                session_name,
                "-F",
                "#{window_index}: #{window_name}",
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
        # Parse the output, filtering out empty lines
        windows = [
            line.strip() for line in result.stdout.strip().split("\n") if line.strip()
        ]
        return windows
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        # Session does not exist or the command failed; return an empty list
        return []
    except Exception as e:
        # Log unexpected errors
        PrettyOutput.auto_print(
            f"⚠️ Unexpected error while listing windows for session '{session_name}': {e}",
            timestamp=None,
        )
        return []


def get_window_pane_count(session_name: str, window_id: str) -> int:
    """Get the number of panels in the specified window of the specified tmux session.

    Args:
        session_name: tmux session name
        window_id: window identifier (index or name, such as "1" or "1: bash")

    Returns:
        int: number of panels; returns 0 if the window does not exist or the command fails

    Note:
        window_id can be the full "index: name" format (e.g., "1: bash"),
        or it can be just the index (e.g., "1").
        If the session does not exist or the command fails, return 0.
    """
    try:
        # Parse window_id: supports both the "index: name" and "index" formats
        # If it contains a colon, extract the index part; otherwise use it directly
        target_window = (
            window_id.split(":")[0].strip() if ":" in window_id else window_id
        )

        # Build the tmux target argument
        target = f"{session_name}:{target_window}"

        result = subprocess.run(
            [
                "tmux",
                "list-panes",
                "-t",
                target,
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
        # Count the output lines (each line represents one pane)
        panes = [
            line.strip() for line in result.stdout.strip().split("\n") if line.strip()
        ]
        return len(panes)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        # Window does not exist or the command failed; return 0
        return 0
    except Exception as e:
        # Log unexpected errors
        PrettyOutput.auto_print(
            f"⚠️ Unexpected error while counting panes for window '{window_id}' in session '{session_name}': {e}",
            timestamp=None,
        )
        return 0


def create_window(
    session_name: str,
    window_name: Optional[str] = None,
    working_dir: Optional[str] = None,
    initial_command: Optional[str] = None,
    stay_in_session_after_exit: bool = True,
) -> Optional[str]:
    """Create a new window in the specified tmux session.

    Args:
        session_name: tmux session name
        window_name: window name (optional)
        working_dir: working directory (optional; None means use the current working directory)
        initial_command: initial command (optional; None means only start the user's shell)
        stay_in_session_after_exit: whether to keep the session active after the command finishes (True means start a shell to keep the session, False means exit directly)

    Returns:
        Optional[str]: the newly created window ID, or None on failure

    Note:
        The created window is in a detached state and will not automatically switch to that window.
        If initial_command is specified, the user's default shell is started after the command finishes to keep the window active.
    """
    # Determine the working directory
    if working_dir is None:
        working_dir = os.getcwd()

    # Get the user's default shell
    user_shell = os.environ.get("SHELL", "/bin/sh")

    # Construct the command
    if initial_command:
        # First switch to the working directory, execute the initial command
        command = f"cd {shlex.quote(working_dir)} && {initial_command}"
        # If the session needs to stay active, start the shell
        if stay_in_session_after_exit:
            command += f'; exec "{user_shell}"'
    else:
        # Just switch to the working directory and start the shell
        command = f'cd {shlex.quote(working_dir)}; exec "{user_shell}"'

    # Construct the tmux new-window command
    tmux_args = [
        "tmux",
        "new-window",
        "-d",  # create a detached window
        "-P",  # print information about the newly created window
        "-F",  # specify the output format (use window_index for subsequent send-keys calls)
        "#{window_index}",
        "-c",  # specify the working directory
        working_dir,
    ]

    # If a window name is specified, add the -n argument
    if window_name:
        tmux_args.extend(["-n", window_name])

    # Add the target session and command
    tmux_args.extend(["-t", session_name, command])

    # Execute the tmux command
    try:
        result = subprocess.run(
            tmux_args,
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
        # Return the newly created window ID
        window_id = result.stdout.strip()
        if window_id:
            return window_id
        else:
            PrettyOutput.auto_print(
                f"⚠️ tmux new-window returned empty window_id for session '{session_name}'",
                timestamp=None,
            )
            PrettyOutput.auto_print(
                f"⚠️ stdout: {result.stdout}",
                timestamp=None,
            )
            return None
    except subprocess.CalledProcessError as e:
        PrettyOutput.auto_print(
            f"⚠️ Failed to create window in session '{session_name}': {e}",
            timestamp=None,
        )
        return None
    except subprocess.TimeoutExpired:
        PrettyOutput.auto_print(
            f"⚠️ Creating window in session '{session_name}' timed out",
            timestamp=None,
        )
        return None
    except Exception as e:
        PrettyOutput.auto_print(
            f"⚠️ Unexpected error creating window in session '{session_name}': {type(e).__name__}: {e}",
            timestamp=None,
        )
        return None


def create_panel(
    session_name: str,
    window_id: str,
    initial_command: str,
    split_direction: str = "h",
    working_dir: Optional[str] = None,
    pane_percentage: Optional[int] = None,
    stay_in_session_after_exit: bool = True,
    shell_fallback: bool = True,
) -> Optional[str]:
    """Create a panel in the specified tmux session and window and execute the initial command.

    Args:
        session_name: tmux session name
        window_id: window identifier (index or name, such as "1" or "1: bash")
        initial_command: the initial command executed in the panel
        split_direction: split direction, "h" means horizontal split (left/right), "v" means vertical split (top/bottom)
        working_dir: working directory, None means use the current working directory
        pane_percentage: pane size percentage (1-99), None means default size
        stay_in_session_after_exit: whether to keep the session active after the command finishes (True means start a shell to keep the session alive, False means exit directly)
        shell_fallback: whether to start a shell as a fallback after the command finishes (True means start a shell, False means do not start a shell and use the process directly as the entry point)

    Returns:
        Optional[str]: the newly created pane ID, returns None on failure

    Note:
        window_id can be the full "index: name" format, or just the index.
        After creating the panel, the user's default shell is started once the command finishes to keep the panel active.
    """
    # Validate the split_direction argument
    if split_direction not in ("h", "v"):
        PrettyOutput.auto_print(
            f"⚠️ Invalid split_direction: '{split_direction}', must be 'h' or 'v'",
            timestamp=None,
        )
        return None

    # Validate the pane_percentage argument
    if pane_percentage is not None and (pane_percentage < 1 or pane_percentage > 99):
        PrettyOutput.auto_print(
            f"⚠️ Invalid pane_percentage: '{pane_percentage}', must be between 1 and 99",
            timestamp=None,
        )
        return None

    # Parse window_id: supports both the "index: name" and "index" formats
    target_window = window_id.split(":")[0].strip() if ":" in window_id else window_id

    # Construct the tmux target argument
    target = f"{session_name}:{target_window}"

    # Determine the working directory
    if working_dir is None:
        working_dir = os.getcwd()

    # Get the user's default shell
    user_shell = os.environ.get("SHELL", "/bin/sh")

    # Construct the command: first switch to the working directory, execute the initial command
    command = f"cd {shlex.quote(working_dir)} && {initial_command}"
    # If the session needs to stay active and shell fallback is allowed, start the shell
    if stay_in_session_after_exit and shell_fallback:
        command += f'; exec "{user_shell}"'

    # Construct the tmux split-window command
    tmux_args = [
        "tmux",
        "split-window",
        "-d",  # create a detached pane to avoid affecting the current pane
        f"-{split_direction}",  # -h horizontal split, -v vertical split
    ]

    # If a pane size is specified, add the -p argument
    if pane_percentage is not None:
        tmux_args.extend(["-p", str(pane_percentage)])

    # Add the target and command
    tmux_args.extend(["-t", target, command])

    # Execute the tmux command to create the pane
    try:
        subprocess.run(
            tmux_args,
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )

        # Get the newly created pane ID (find the most recent pane via list-panes)
        list_args = [
            "tmux",
            "list-panes",
            "-t",
            target,
            "-F",
            "#{pane_index}",
        ]
        list_result = subprocess.run(
            list_args,
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )

        # Find the most recent pane (the one with the largest index)
        panes = list_result.stdout.strip().split("\n")
        if not panes or not panes[0]:
            PrettyOutput.auto_print(
                f"⚠️ Failed to list panes for target '{target}'",
                timestamp=None,
            )
            return None

        # The last pane is the most recent one
        latest_pane_index = panes[-1]

        # Get the full pane_id
        get_id_args = [
            "tmux",
            "display-message",
            "-t",
            f"{target}.{latest_pane_index}",
            "-p",
            "#{pane_id}",
        ]
        id_result = subprocess.run(
            get_id_args,
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )

        pane_id = id_result.stdout.strip()
        if pane_id:
            return pane_id
        else:
            PrettyOutput.auto_print(
                f"⚠️ Failed to get pane_id for target '{target}'",
                timestamp=None,
            )
            PrettyOutput.auto_print(
                f"⚠️ list-panes output: {list_result.stdout.strip()}",
                timestamp=None,
            )
            return None
    except subprocess.CalledProcessError as e:
        stderr_output = e.stderr.strip() if e.stderr else "(no stderr output)"
        PrettyOutput.auto_print(
            f"⚠️ Failed to create panel in window '{window_id}' of session '{session_name}': {e}",
            timestamp=None,
        )
        PrettyOutput.auto_print(
            f"⚠️ tmux stderr: {stderr_output}",
            timestamp=None,
        )
        return None
    except subprocess.TimeoutExpired:
        PrettyOutput.auto_print(
            f"⚠️ Creating panel in window '{window_id}' of session '{session_name}' timed out",
            timestamp=None,
        )
        return None
    except Exception as e:
        PrettyOutput.auto_print(
            f"⚠️ Unexpected error creating panel in window '{window_id}' of session '{session_name}': {type(e).__name__}: {e}",
            timestamp=None,
        )
        return None


def set_window_tiled_layout(session_name: str, window_id: Optional[str] = None) -> bool:
    """Set the window layout of the specified tmux session to tiled.

    Args:
        session_name: tmux session name
        window_id: window identifier (index or name, such as "1" or "1: bash")
                     If None, set the session's current window

    Returns:
        bool: whether the layout was set successfully (True means success, False means failure)

    Note:
        window_id can be the full "index: name" format, or just the index.
        If window_id is None, set the currently active window in the session.
        The tiled layout allocates space evenly among all panes.
    """
    # Construct the tmux target argument
    if window_id is None:
        # Set the session's current window
        target = session_name
    else:
        # Parse window_id: supports both the "index: name" and "index" formats
        target_window = (
            window_id.split(":")[0].strip() if ":" in window_id else window_id
        )
        target = f"{session_name}:{target_window}"

    # Execute the tmux select-layout command
    try:
        subprocess.run(
            ["tmux", "select-layout", "-t", target, "tiled"],
            check=True,
            timeout=5,
        )
        return True
    except subprocess.CalledProcessError as e:
        PrettyOutput.auto_print(
            f"⚠️ Failed to set tiled layout for window '{window_id or 'current'}' in session '{session_name}': {e}",
            timestamp=None,
        )
        return False
    except subprocess.TimeoutExpired:
        PrettyOutput.auto_print(
            f"⚠️ Setting tiled layout for window '{window_id or 'current'}' in session '{session_name}' timed out",
            timestamp=None,
        )
        return False


def find_or_create_haijunbot_session(
    force_create: bool = True, initial_command: Optional[str] = None
) -> Optional[str]:
    """Find or create a haijunbot session.

    Prefer to find an existing haijunbot session; if found, return the session name,
    otherwise create a new session.

    Args:
        force_create: whether to create a new session when none is found
        initial_command: initial command (optional); if specified, start with that command directly when creating the session

    Returns:
        Optional[str]: the found or created session name; returns None if not found and not created
    """
    # First try to find an existing session
    existing_session = _find_haijunbot_session()
    if existing_session:
        return existing_session

    # No existing session found
    if not force_create:
        return None

    # Create a new session
    session_name = _generate_session_name()
    try:
        if initial_command:
            # Create a new detached session, starting with the specified command directly
            subprocess.run(
                ["tmux", "new-session", "-d", "-s", session_name, initial_command],
                check=True,
                timeout=10,
            )
        else:
            # Create a new detached session, using the true command as the initial pane (exits immediately)
            # This avoids the default shell pane while keeping the window alive
            subprocess.run(
                ["tmux", "new-session", "-d", "-s", session_name, "true"],
                check=True,
                timeout=10,
            )
        return session_name
    except subprocess.CalledProcessError as e:
        PrettyOutput.auto_print(
            f"⚠️ Failed to create tmux session '{session_name}': {e}",
            timestamp=None,
        )
        return None
    except subprocess.TimeoutExpired:
        PrettyOutput.auto_print(
            f"⚠️ Creating tmux session '{session_name}' timed out",
            timestamp=None,
        )
        return None


def get_session_current_window(session_name: str) -> Optional[str]:
    """Get the current window index of the specified tmux session.

    Args:
        session_name: tmux session name

    Returns:
        Optional[str]: the current window index (such as '0', '1'), returns None on failure
    """
    tmux_path = shutil.which("tmux")
    if tmux_path is None:
        return None

    try:
        # Get all windows of the session; the current window is marked with *
        result = subprocess.run(
            [
                "tmux",
                "list-windows",
                "-t",
                session_name,
                "-F",
                "#{window_index}:#{window_flags}",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            return None

        # Parse the output to find the window marked with * (the current window)
        for line in result.stdout.strip().split("\n"):
            if "*" in line:
                # Return the window index part (before the colon)
                window_idx = line.split(":")[0].strip()
                return window_idx if window_idx else None
        return None
    except Exception:
        return None


def get_current_session_name() -> Optional[str]:
    """Get the current tmux session name.

    Returns:
        Optional[str]: the current session name; returns None if not in a tmux environment or on failure
    """
    tmux_path = shutil.which("tmux")
    if tmux_path is None:
        return None

    try:
        result = subprocess.run(
            ["tmux", "display-message", "-p", "#S"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            session_name = result.stdout.strip()
            return session_name if session_name else None
        return None
    except Exception:
        return None


def get_current_window_index() -> Optional[str]:
    """Get the index of the current tmux window.

    Returns:
        Optional[str]: the current window index (such as '0', '1'); returns None if not in a tmux environment or on failure
    """
    tmux_path = shutil.which("tmux")
    if tmux_path is None:
        return None

    try:
        result = subprocess.run(
            ["tmux", "display-message", "-p", "#{window_index}"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            window_index = result.stdout.strip()
            return window_index if window_index else None
        return None
    except Exception:
        return None


def has_session(session_name: str) -> bool:
    """Check whether the specified tmux session exists.

    Args:
        session_name: session name

    Returns:
        bool: whether the session exists
    """
    tmux_path = shutil.which("tmux")
    if tmux_path is None:
        return False

    try:
        result = subprocess.run(
            ["tmux", "has-session", "-t", session_name],
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0
    except Exception:
        return False


def send_command_to_window(
    session_name: str, window_id: str, command: list[str]
) -> bool:
    """Send a command to the initial pane of the specified window.

    Args:
        session_name: session name
        window_id: window index
        command: list of command (will be shell-escaped)

    Returns:
        bool: whether the send succeeded
    """
    import shlex

    tmux_path = shutil.which("tmux")
    if tmux_path is None:
        return False

    # Convert the command to a string and escape it correctly
    cmd_str = " ".join(shlex.quote(arg) for arg in command)

    try:
        subprocess.run(
            ["tmux", "send-keys", "-t", f"{session_name}:{window_id}", cmd_str, "C-m"],
            capture_output=True,
            timeout=10,
        )
        return True
    except Exception:
        return False


def dispatch_command_to_panel(
    shell_command: str,
    max_panes_per_window: int = 4,
    stay_in_session_after_exit: bool = True,
    shell_fallback: bool = True,
) -> Optional[str]:
    """Schedule a command to be executed in a panel of the current tmux window.

    Simplified implementation: always create a panel in the current window, no longer create a new window.
    The max_panes_per_window argument is kept for compatibility but no longer takes effect.

    Args:
        shell_command: the shell command to execute
        max_panes_per_window: the maximum number of panes per window (kept for compatibility, no longer takes effect)
        stay_in_session_after_exit: whether to keep the session active after the command finishes
        shell_fallback: whether to start a shell as a fallback after the command finishes (True means start a shell, False means do not start a shell and use the process directly as the entry point)
    """
    # Set environment variables before the command so the child process knows it was started by hcad/hjbd
    # This way the enable_tmux configuration can be ignored
    shell_command_with_env = f"HAIJUNBOT_DISPATCHER_CALL=1 {shell_command}"

    # Check whether tmux is installed
    tmux_path = shutil.which("tmux")
    if tmux_path is None:
        PrettyOutput.auto_print("⚠️ tmux is not installed", timestamp=None)
        return None

    # First try to find an existing session
    existing_session = _find_haijunbot_session()

    if existing_session:
        # Use the existing session, create a panel in the current window
        PrettyOutput.auto_print(
            f"ℹ️ Using existing tmux session: {existing_session}",
            timestamp=None,
        )

        # Get the current window index
        current_window = get_session_current_window(existing_session)
        if not current_window:
            PrettyOutput.auto_print(
                f"⚠️ Unable to get the current window of session '{existing_session}'",
                timestamp=None,
            )
            return None

        # Create a panel in the current window
        pane_id = create_panel(
            session_name=existing_session,
            window_id=current_window,
            initial_command=shell_command_with_env,
            split_direction="h",
            stay_in_session_after_exit=stay_in_session_after_exit,
            shell_fallback=shell_fallback,
        )
        if pane_id:
            PrettyOutput.auto_print(
                f"✅ Successfully created panel {pane_id} in current window {current_window}",
                timestamp=None,
            )
            return existing_session
        else:
            PrettyOutput.auto_print(
                f"❌ Failed to create panel in window {current_window} of session '{existing_session}'",
                timestamp=None,
            )
            PrettyOutput.auto_print(
                f"🔍 Command: {shell_command[:100]}{'...' if len(shell_command) > 100 else ''}",
                timestamp=None,
            )
            return None
    else:
        # No existing session, create a new session and start with the main process directly
        new_session = find_or_create_haijunbot_session(
            force_create=True, initial_command=shell_command_with_env
        )
        if not new_session:
            PrettyOutput.auto_print(
                "⚠️ Failed to create haijunbot session",
                timestamp=None,
            )
            return None

        PrettyOutput.auto_print(
            f"✅ Successfully created session '{new_session}' with main process",
            timestamp=None,
        )
        return new_session


def _dispatch_to_existing_haijunbot_session(
    task_arg: Optional[str],
    argv: list[str],
    stay_in_session_after_exit: bool = True,
    shell_fallback: bool = True,
) -> bool:
    """Dispatch the task to be executed in a panel of an existing haijunbot tmux session.

    This is a fallback: when not in a tmux environment, try to find a session created by haijunbot
    and create a panel in it to execute the command. If no session is found, create a new session.

    Args:
        task_arg: task content (deprecated, kept for compatibility)
        argv: current command-line arguments (--dispatch needs to be filtered out)
        stay_in_session_after_exit: whether to keep the session active after the command finishes (True means start a shell to keep the session alive, False means exit directly)
        shell_fallback: whether to start a shell as a fallback after the command finishes (True means start a shell, False means do not start a shell and use the process directly as the entry point)

    Returns:
        bool: whether the dispatch succeeded (True means success, False means failure)
    """
    # Find or create a haijunbot session
    session_name = find_or_create_haijunbot_session(force_create=True)
    if not session_name:
        PrettyOutput.auto_print(
            "❌ Unable to find or create tmux session",
            timestamp=None,
        )
        return False

    PrettyOutput.auto_print(
        f"ℹ️ Using tmux session: {session_name}",
        timestamp=None,
    )

    # Filter out the --dispatch/-d argument to avoid recursive dispatching
    filtered_argv = []
    skip_next = False
    for i, arg in enumerate(argv):
        if skip_next:
            skip_next = False
            continue
        if arg == "--dispatch" or arg == "-d":
            continue
        elif arg.startswith("--dispatch=") or arg.startswith("-d="):
            continue
        else:
            filtered_argv.append(arg)

    # Construct the command string
    executable = sys.executable
    quoted_args = [shlex.quote(arg) for arg in filtered_argv]
    user_shell = os.environ.get("SHELL", "/bin/sh")
    cwd = os.getcwd()
    command = f"cd {shlex.quote(cwd)} && {executable} {' '.join(quoted_args)}"
    # If the session needs to stay active and shell fallback is allowed, start the shell
    if stay_in_session_after_exit and shell_fallback:
        command += f'; exec "{user_shell}"'

    # Get the session's current window
    current_window = get_session_current_window(session_name)
    if not current_window:
        PrettyOutput.auto_print(
            f"⚠️ Unable to get the current window of session '{session_name}', creating a new session",
            timestamp=None,
        )
        # When the current window cannot be obtained, create a new session and start with the main process
        new_session = find_or_create_haijunbot_session(
            force_create=True, initial_command=command
        )
        if not new_session:
            PrettyOutput.auto_print(
                "⚠️ Failed to create new session",
                timestamp=None,
            )
            return False

        PrettyOutput.auto_print(
            f"✅ Successfully created new session '{new_session}' and started the task",
            timestamp=None,
        )
        return True

    # Create a panel in the current window
    pane_id = create_panel(
        session_name=session_name,
        window_id=current_window,
        initial_command=command,
        split_direction="h",
        stay_in_session_after_exit=stay_in_session_after_exit,
        shell_fallback=shell_fallback,
    )
    if not pane_id:
        PrettyOutput.auto_print(
            f"⚠️ Failed to create panel in window '{current_window}'",
            timestamp=None,
        )
        return False

    # Panel created successfully
    PrettyOutput.auto_print(
        f"✅ Task dispatched to a panel of tmux session '{session_name}'",
        timestamp=None,
    )
    return True
