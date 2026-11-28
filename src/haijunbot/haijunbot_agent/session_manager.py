# -*- coding: utf-8 -*-
import glob
import json
import os
import subprocess
from datetime import datetime
from typing import TYPE_CHECKING
from typing import Any
from typing import Dict
from typing import List
from typing import Optional
from typing import Tuple
from typing import Union
from typing import cast

from haijunbot.haijunbot_platform.content_types import ContentBlock
from haijunbot.haijunbot_utils.output import PrettyOutput
from haijunbot.haijunbot_utils.input import get_single_line_input
from haijunbot.haijunbot_utils.utils import atomic_write_json
from haijunbot.haijunbot_utils.utils import cleanup_stale_tmp_files

if TYPE_CHECKING:
    from haijunbot.haijunbot_platform.base import BasePlatform
    from haijunbot.haijunbot_agent import Agent


class SessionManager:
    """
    Manages the session state of an agent, including conversation history,
    user data, and persistence.
    """

    def __init__(
        self, model: "BasePlatform", agent_name: str, agent: Optional["Agent"] = None
    ):
        self.model = model
        self.agent_name = agent_name
        self.agent = agent  # Add agent reference
        self.prompt: Union[str, List[ContentBlock]] = ""
        self.user_data: Dict[str, Any] = {}
        self.addon_prompt: str = ""
        self.conversation_length: int = 0
        self.last_restored_session: Optional[str] = (
            None  # Record the last saved or restored session file path
        )
        self.current_session_name: Optional[str] = None  # Current session name
        self.non_interactive: bool = False  # Whether in non-interactive mode

    def set_user_data(self, key: str, value: Any) -> None:
        """Sets a value in the user data dictionary."""
        self.user_data[key] = value

    def get_user_data(self, key: str) -> Optional[Any]:
        """Gets a value from the user data dictionary."""
        return self.user_data.get(key)

    def set_addon_prompt(self, addon_prompt: str) -> None:
        """Sets the addon prompt for the next model call."""
        self.addon_prompt = addon_prompt

    def _generate_session_name(self) -> str:
        """Generate a session name from the conversation history using an LLM

        Preferentially uses the cheap model to generate a concise session name,
        falling back to the current conversation model on failure, and returns the default name if that also fails.

        Returns:
            str: Session name generated from the conversation history using an LLM
        """
        import re

        # Extract text from the conversation history
        conversation_text = ""
        try:
            messages = self.model.get_messages()
            for msg in messages:
                role = msg.get("role", "")
                content = msg.get("content", "")
                # Skip the context-compression summary messages injected by HaijunBot (starting with [History Summary]),
                # to avoid system-level metadata (code change stats / task list status, etc.) polluting the session topic detection
                if self._is_compressed_summary_msg(msg):
                    continue
                # Extract text content from user and assistant
                if role in ["user", "assistant"] and content:
                    if isinstance(content, str):
                        conversation_text += content + " "
                    elif isinstance(content, list):
                        # Handle multimodal message lists
                        for block in content:
                            if isinstance(block, dict) and block.get("type") == "text":
                                conversation_text += block.get("text", "") + " "
        except Exception:
            pass

        # If the conversation history is empty, return the default name
        if not conversation_text.strip():
            return "Unnamed Session"

        # Truncate overly long conversation text to avoid exceeding the model context
        if len(conversation_text) > 4000:
            conversation_text = conversation_text[:4000]

        prompt = (
            "Please generate a short, fitting session name for this conversation based on the following content.\n"
            "Requirements:\n"
            "1. Summarize the conversation topic in English, keeping the length within 2-10 words\n"
            "2. Do not use punctuation, quotes, or any special characters\n"
            "3. Output only the session name itself, with no explanation or prefix/suffix\n\n"
            f"Conversation content:\n{conversation_text}"
        )

        # Try generating the session name with the cheap model and the current conversation model in turn
        for platform in self._iter_name_platforms():
            try:
                result = platform.complete(prompt)
                if result and result != "<output interrupted by user>":
                    # Clean special characters, keeping only Chinese, English, digits, underscores, and hyphens
                    session_name = re.sub(r"[^\u4e00-\u9fa5a-zA-Z0-9 _-]", "", result).strip()
                    # Limit the length (at most 15 characters)
                    if len(session_name) > 30:
                        session_name = session_name[:30].rstrip()
                    if session_name:
                        return session_name
            except Exception:
                # Current platform generation failed, try the next platform
                continue

        # Return the default name when all platforms fail
        return "Unnamed Session"

    def _is_compressed_summary_msg(self, msg: Dict[str, Any]) -> bool:
        """Determine whether a message is a context-compression summary message injected by HaijunBot.

        The compressed summary (sliding window / pre-compression path _format_compressed_summary)
        starts with "[History Summary]" and is inserted into the history as a user message, containing code change stats, task list status, and other system-level metadata,
        and should not participate in session topic detection.
        """
        if msg.get("role") != "user":
            return False
        content = msg.get("content", "")
        if isinstance(content, str):
            return content.lstrip().startswith("[History Summary]")
        if isinstance(content, list):
            # Multimodal message: check whether the first text block starts with [History Summary]
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    text = block.get("text", "")
                    if isinstance(text, str) and text.lstrip().startswith("[History Summary]"):
                        return True
                    break
        return False

    def _iter_name_platforms(self):
        """Return a platform iterator for generating session names (cheap model first, falling back to the current conversation model)"""
        try:
            from haijunbot.haijunbot_platform.registry import PlatformRegistry

            cheap = PlatformRegistry.get_global_platform_registry().get_cheap_platform()
            if cheap is not None:
                yield cheap
        except Exception:
            pass

        # Fall back to the current conversation model (stateless completion, does not affect the main conversation history)
        yield self.model

    def _list_session_files(self) -> List[str]:
        """
        Scan and return the list of all session files matching the current session.

        Returns:
            List of session file paths, sorted by filename.
        """
        session_dir = os.path.join(os.getcwd(), ".haijunbot", "sessions")
        if not os.path.exists(session_dir):
            return []

        # Match session files: {session_name}_saved_session_{agent_name}_{timestamp}.json
        pattern = os.path.join(
            session_dir,
            f"*saved_session_{self.agent_name}_*.json",
        )

        files = sorted(glob.glob(pattern))

        # Filter out auxiliary files (commit file, tasklist file, state file, code_agent file)
        session_files = []
        for f in files:
            basename = os.path.basename(f)
            # Exclude auxiliary files ending with _commit.json, _tasklist.json, _state.json, and _code_agent.json
            if not (
                basename.endswith("_commit.json")
                or basename.endswith("_tasklist.json")
                or basename.endswith("_state.json")
                or basename.endswith("_code_agent.json")
                or basename.endswith("_codeagent.json")  # Compatible with old format
            ):
                session_files.append(f)

        return session_files

    def _extract_timestamp(self, filename: str) -> Optional[str]:
        """
        Extract the timestamp from a session filename.

        Args:
            filename: Session filename (without path).

        Returns:
            Timestamp string (e.g. "20250106_084038"), or None if there is no timestamp.
        """
        import re

        basename = os.path.basename(filename)
        # New format: {session_name}_saved_session_{agent_name}_{timestamp}.json
        # Timestamp format: YYYYMMDD_HHMMSS (8-digit date_6-digit time)
        # Use a regular expression to precisely match the timestamp format
        # \d{8}_\d{6} matches 8 digits + underscore + 6 digits
        timestamp_pattern = r"_(\d{8}_\d{6})\.json$"
        match = re.search(timestamp_pattern, basename)

        if match:
            return match.group(1)

        return None

    def _read_session_name(self, session_file: str) -> Optional[str]:
        """
        Read the session name from the session's commit info file.

        Args:
            session_file: Session file path

        Returns:
            Session name, or None if it does not exist.
        """
        try:
            # Build the corresponding _commit.json file path
            commit_file = (
                session_file[:-5] + "_commit.json"
            )  # Remove ".json" and append "_commit.json"

            if not os.path.exists(commit_file):
                return None

            with open(commit_file, "r", encoding="utf-8") as f:
                commit_info = cast(Dict[str, Any], json.load(f))
                session_name = commit_info.get("session_name")
                # Ensure the return value type is Optional[str]
                if session_name is not None and isinstance(session_name, str):
                    return cast(Optional[str], session_name)
                return None

        except Exception:
            # A read failure does not affect the main flow, return None
            return None

    def _parse_session_files(
        self,
    ) -> List[Tuple[str, Optional[str], Optional[str], str]]:
        """
        Parse the session file list and return a list containing the file path, timestamp, session name, and commit status.

        Returns:
            List of session info, each element is (file path, timestamp, session name, commit status), sorted by timestamp descending.
            If a file has no timestamp, the timestamp is None; if it has no session name, the session name is None.
            Possible commit status values: "consistent" (consistent), "inconsistent" (inconsistent), "no_commit" (no commit info)
        """
        files = self._list_session_files()

        sessions = []
        for file_path in files:
            timestamp = self._extract_timestamp(file_path)
            session_name = self._read_session_name(file_path)
            commit_status = self._check_commit_status(file_path)
            sessions.append((file_path, timestamp, session_name, commit_status))

        # Sort by timestamp descending (newest first), files without a timestamp go last
        sessions.sort(key=lambda x: (x[1] is None, x[1] or ""), reverse=True)

        return sessions

    def _check_commit_status(self, session_file: str) -> str:
        """
        Check the commit status of a session file.

        Args:
            session_file: Session file path

        Returns:
            str: Commit status, possible values:
                - "consistent": commit is consistent (green)
                - "inconsistent": commit is inconsistent (red)
                - "no_commit": no commit info (yellow)
        """
        try:
            # Read the commit at save time from the _commit.json file
            commit_file = session_file[:-5] + "_commit.json"

            # If the commit file does not exist, return no commit info
            if not os.path.exists(commit_file):
                return "no_commit"

            with open(commit_file, "r", encoding="utf-8") as f:
                commit_data = json.load(f)

            saved_commit = commit_data.get("current_commit", "")

            # If the session file has no saved commit info, return no commit info
            if not saved_commit:
                return "no_commit"

            # Get the current HEAD commit
            try:
                result = subprocess.run(
                    ["git", "rev-parse", "HEAD"],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                current_commit = result.stdout.strip()

                # If not in a git repository, return no commit info
                if result.returncode != 0:
                    return "no_commit"

            except Exception:
                # git command execution failed, return no commit info
                return "no_commit"

            # Check whether the commit is consistent
            if saved_commit == current_commit:
                return "consistent"
            else:
                return "inconsistent"

        except Exception:
            # Any exception returns no commit info
            return "no_commit"

    def _find_sessions_by_commit(
        self, commit_hash: str
    ) -> List[Tuple[str, Optional[str], Optional[str], str]]:
        """
        Find the list of sessions matching the specified commit.

        Args:
            commit_hash: The commit hash to match

        Returns:
            List of matching sessions, each element is (file path, timestamp, session name), sorted by timestamp descending.
        """
        files = self._list_session_files()
        matching_sessions = []

        for file_path in files:
            try:
                # Read the corresponding _commit.json file
                commit_file = file_path[:-5] + "_commit.json"
                if not os.path.exists(commit_file):
                    continue

                with open(commit_file, "r", encoding="utf-8") as f:
                    commit_data = json.load(f)

                saved_commit = commit_data.get("current_commit", "")
                # Check whether the commit matches
                if saved_commit == commit_hash:
                    timestamp = self._extract_timestamp(file_path)
                    session_name = self._read_session_name(file_path)
                    commit_status = self._check_commit_status(file_path)
                    matching_sessions.append(
                        (file_path, timestamp, session_name, commit_status)
                    )

            except Exception:
                # Skip the session when reading fails
                continue

        # Sort by timestamp descending (newest first)
        matching_sessions.sort(key=lambda x: (x[1] is None, x[1] or ""), reverse=True)
        return matching_sessions

    def _prompt_to_restore_matching_sessions(
        self, matching_sessions: List[Tuple[str, Optional[str], Optional[str], str]]
    ) -> Optional[str]:
        """
        Prompt the user to choose whether to restore the matching sessions.

        Args:
            matching_sessions: List of matching sessions, each element is (file path, timestamp, session name, commit status)

        Returns:
            The restored session file path, or None if the user chooses not to restore
        """
        if not matching_sessions:
            return None

        PrettyOutput.auto_print("🔍 Detected historical sessions consistent with the current commit:")
        for idx, (file_path, timestamp, session_name, commit_status) in enumerate(
            matching_sessions, 1
        ):
            time_str = timestamp if timestamp else "(no timestamp)"
            name_str = f" - {session_name}" if session_name else ""
            PrettyOutput.auto_print(
                f"  {idx}. {os.path.basename(file_path)} [{time_str}]{name_str}"
            )

        try:
            while True:
                choice = get_single_line_input(
                    "\nRestore session? (enter a number to restore, press Enter to skip): "
                ).strip()

                # Press Enter directly, do not restore
                if not choice:
                    PrettyOutput.auto_print("⏭️  Skipping session restore, continuing normal flow.")
                    return None

                # Validate whether the input is a number
                if not choice.isdigit():
                    PrettyOutput.auto_print("❌ Invalid choice, please enter a number or press Enter to skip.")
                    continue

                choice_idx = int(choice) - 1

                # Validate whether the number is within the valid range
                if choice_idx < 0 or choice_idx >= len(matching_sessions):
                    PrettyOutput.auto_print(
                        f"❌ Invalid choice, please enter a number between 1 and {len(matching_sessions)}, or press Enter to skip."
                    )
                    continue

                # Input is valid, return the selected session file
                return matching_sessions[choice_idx][0]

        except (EOFError, KeyboardInterrupt):
            PrettyOutput.auto_print("⚠️  Session restore canceled.")
            return None

    def build_session_snapshot(
        self, timestamp: Optional[str] = None
    ) -> Optional[Tuple[str, List[Tuple[str, Any, Optional[Any]]]]]:
        """Construct in memory the contents of all files needed for a full session flush (without writing to disk).

        Returns (session_file, files), where files is
        [(file_path, data, default_encoder), ...], covering:
        - The main session file (messages)
        - _commit.json
        - _state.json
        - _tasklist.json

        This method is the shared data-construction entry point for save_session and the real-time save daemon,
        ensuring that the filenames and content formats written by both paths are exactly the same.

        Args:
            timestamp: Session timestamp (%Y%m%d_%H%M%S); uses the current time if empty.

        Returns:
            (session_file, files); returns None if there are no user messages (nothing to save).
        """
        session_dir = os.path.join(os.getcwd(), ".haijunbot", "sessions")
        os.makedirs(session_dir, exist_ok=True)
        if not timestamp:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Determine the session name
        if self.current_session_name:
            session_name = self.current_session_name
        else:
            session_name = self._generate_session_name()
            self.current_session_name = session_name

        session_file = os.path.join(
            session_dir,
            f"{session_name}_saved_session_{self.agent_name}_{timestamp}.json",
        )

        # Check whether there are user messages; do not save if there are none
        try:
            has_user_message = any(
                msg.get("role") == "user" for msg in self.model.get_messages()
            )
            if not has_user_message:
                return None
        except Exception:
            # If the check fails (e.g. messages does not exist), still perform the save for safety
            pass

        # Main session file content (consistent with BasePlatform.save)
        try:
            messages = self.model.get_messages()
        except Exception:
            messages = []
        main_data: Dict[str, Any] = {"messages": messages}

        files: List[Tuple[str, Any, Optional[Any]]] = [
            (session_file, main_data, None),
        ]

        # _commit.json
        commit_info = self._build_commit_info(session_file)
        if commit_info is not None:
            files.append((session_file[:-5] + "_commit.json", commit_info, None))

        # _state.json
        state_data = self._build_agent_state(timestamp)
        if state_data is not None:
            from haijunbot.haijunbot_agent import SafeEncoder

            state_file = os.path.join(
                session_dir, f"{self._get_session_file_prefix()}_{timestamp}_state.json"
            )
            files.append((state_file, state_data, SafeEncoder().default))

        # _tasklist.json
        tasklist_data = self._build_task_lists()
        if tasklist_data is not None:
            tasklist_file = os.path.join(
                session_dir, f"{self._get_session_file_prefix()}_tasklist.json"
            )
            files.append((tasklist_file, tasklist_data, None))

        return session_file, files

    def save_session(self) -> bool:
        """Saves the current session state to a file."""
        session_dir = os.path.join(os.getcwd(), ".haijunbot", "sessions")
        os.makedirs(session_dir, exist_ok=True)
        # Clean up atomic-write temp files left over from the last time the process was force-killed
        cleanup_stale_tmp_files(session_dir)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Determine the session name
        if self.current_session_name:
            # Already has a session name (inherited from a restored session), use it directly
            session_name = self.current_session_name
        else:
            # New session, use TextRank to generate a name from the conversation history
            session_name = self._generate_session_name()
            PrettyOutput.auto_print(f"📝 Generated session name: {session_name}")

            self.current_session_name = session_name

        # Use session_name as the filename prefix
        session_file = os.path.join(
            session_dir,
            f"{session_name}_saved_session_{self.agent_name}_{timestamp}.json",
        )

        # Check whether there are user messages; do not save if there are none
        try:
            has_user_message = any(
                msg.get("role") == "user" for msg in self.model.get_messages()
            )
            if not has_user_message:
                # No user messages, do not save the session
                return False
        except Exception:
            # If the check fails (e.g. messages does not exist), still perform the save for safety
            pass

        result = self.model.save(session_file)

        # After a successful save, write the commit info to the auxiliary file
        if result:
            self._save_commit_info(session_file)
            # Save the Agent runtime state
            self._save_agent_state(timestamp)
            # Save the task lists
            self._save_task_lists()
            # Clean up old session files (keep at most 10)
            self._cleanup_old_sessions(session_dir)
            # Update the last saved session file path
            self.last_restored_session = session_file

        return result

    def _build_commit_info(self, session_file: str) -> Optional[Dict[str, Any]]:
        """Construct in memory the contents of _commit.json (without writing to disk).

        Args:
            session_file: Session file path (used to extract the timestamp)

        Returns:
            Commit info dict; returns None if construction fails.
        """
        try:
            from haijunbot.haijunbot_utils.git_utils import get_latest_commit_hash

            # Get the current commit and start_commit (if any)
            current_commit = get_latest_commit_hash()

            # Get start_commit (prefer the agent attribute, fall back to user_data)
            start_commit = None
            last_backup_commit = None
            if self.agent:
                # Prefer checking the agent's start_commit attribute (CodeAgent uses this approach)
                if hasattr(self.agent, "start_commit"):
                    start_commit = self.agent.start_commit
                # Also save last_backup_commit (if any)
                if hasattr(self.agent, "last_backup_commit"):
                    last_backup_commit = self.agent.last_backup_commit
                # Fallback: if there is no attribute, try to get it from user_data
                elif hasattr(self.agent, "get_user_data"):
                    start_commit = self.agent.get_user_data("start_commit")

            # Get metadata
            agent_name = self.agent_name

            # Extract the timestamp from the session file path (reuse the _extract_timestamp logic)
            timestamp_str = self._extract_timestamp(session_file)
            if timestamp_str:
                # Convert the timestamp string to ISO format
                try:
                    dt = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
                    timestamp_iso = dt.isoformat()
                except Exception:
                    timestamp_iso = datetime.now().isoformat()
            else:
                timestamp_iso = datetime.now().isoformat()

            # Build the commit info (containing all fields)
            commit_info = {
                "current_commit": current_commit,
                "agent_name": agent_name,
                "timestamp": timestamp_iso,
            }
            if start_commit:
                commit_info["start_commit"] = start_commit
            if last_backup_commit:
                commit_info["last_backup_commit"] = last_backup_commit
            if self.current_session_name:
                commit_info["session_name"] = self.current_session_name

            return commit_info

        except Exception as e:
            # A failure to construct the commit info does not affect the main flow
            PrettyOutput.auto_print(f"⚠️  Failed to save commit info: {e}")
            return None

    def _save_commit_info(self, session_file: str) -> None:
        """
        Save the commit info to the auxiliary file.

        Args:
            session_file: Session file path
        """
        try:
            commit_info = self._build_commit_info(session_file)
            if commit_info is None:
                return

            # Write the _commit.json file
            commit_file = (
                session_file[:-5] + "_commit.json"
            )  # Remove ".json" and append "_commit.json"
            atomic_write_json(commit_file, commit_info, indent=4, ensure_ascii=False)

        except Exception as e:
            # A failure to save the commit info does not affect the main flow
            PrettyOutput.auto_print(f"⚠️  Failed to save commit info: {e}")

    def _cleanup_old_sessions(self, session_dir: str) -> None:
        """
        Clean up old session files, keeping at most the 10 most recent sessions.

        Args:
            session_dir: Directory where session files reside
        """
        try:
            # Match the session file pattern
            pattern = os.path.join(
                session_dir,
                f"*saved_session_{self.agent_name}_*.json",
            )

            # Get all matching files
            all_files = glob.glob(pattern)

            # Filter out auxiliary files, keeping only the main session files
            session_files = []
            for f in all_files:
                basename = os.path.basename(f)
                # Exclude auxiliary files
                if not (
                    basename.endswith("_commit.json")
                    or basename.endswith("_tasklist.json")
                    or basename.endswith("_state.json")
                    or basename.endswith("_code_agent.json")
                    or basename.endswith("_codeagent.json")  # Compatible with old format
                ):
                    # Extract the timestamp and sort
                    timestamp = self._extract_timestamp(f)
                    session_files.append((f, timestamp))

            # Sort by timestamp descending (newest first)
            session_files.sort(key=lambda x: (x[1] is None, x[1] or ""), reverse=True)

            # If there are more than 10, delete the oldest
            if len(session_files) > 10:
                # Delete all sessions from the 11th onward
                for session_file, _ in session_files[10:]:
                    try:
                        # Delete the main session file
                        if os.path.exists(session_file):
                            os.remove(session_file)

                        # Delete the corresponding auxiliary files
                        base_path = session_file[:-5]  # Remove ".json"
                        auxiliary_suffixes = [
                            "_commit.json",
                            "_tasklist.json",
                            "_state.json",
                            "_code_agent.json",
                            "_codeagent.json",  # Compatible with old format
                        ]

                        for suffix in auxiliary_suffixes:
                            auxiliary_file = base_path + suffix
                            if os.path.exists(auxiliary_file):
                                os.remove(auxiliary_file)
                    except Exception as e:
                        # A delete failure does not affect the cleanup of other files
                        PrettyOutput.auto_print(f"⚠️  Failed to delete old session file: {e}")
        except Exception as e:
            # An error during cleanup should not affect the save functionality
            PrettyOutput.auto_print(f"⚠️  Error while cleaning up old session files: {e}")

    def _check_commit_consistency(self, session_file: str) -> bool:
        """
        Check whether the commit at the time the session file was saved matches the current commit.

        Args:
            session_file: Session file path

        Returns:
            bool: True means consistent or the user chose to continue, False means the user canceled
        """
        try:
            # Read the commit at save time from the _commit.json file
            commit_file = session_file[:-5] + "_commit.json"

            # If the commit file does not exist, skip the check
            if not os.path.exists(commit_file):
                return True

            with open(commit_file, "r", encoding="utf-8") as f:
                commit_data = json.load(f)

            saved_commit = commit_data.get("current_commit", "")

            # If the session file has no saved commit info, skip the check
            if not saved_commit:
                PrettyOutput.auto_print(
                    "ℹ️  Commit file exists but is missing the current_commit field, skipping consistency check"
                )
                return True

            # Get the current HEAD commit
            try:
                result = subprocess.run(
                    ["git", "rev-parse", "HEAD"],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                current_commit = result.stdout.strip()

                # If not in a git repository, skip the check
                if result.returncode != 0:
                    return True

            except Exception:
                # git command execution failed, skip the check
                return True

            # Check whether the commit is consistent
            if saved_commit == current_commit:
                PrettyOutput.auto_print("✅ Git commit consistency check passed")
                PrettyOutput.auto_print(f"   Commit at save time: {saved_commit[:12]}")
                PrettyOutput.auto_print(f"   Current commit:  {current_commit[:12]}")
                return True

            # Commit is inconsistent, show a warning and ask the user
            PrettyOutput.auto_print("")
            PrettyOutput.auto_print("⚠️  ==============================================")
            PrettyOutput.auto_print("⚠️  Git Commit Inconsistency Warning")
            PrettyOutput.auto_print("⚠️  ==============================================")
            PrettyOutput.auto_print("")
            PrettyOutput.auto_print(f"Commit when the session was saved: {saved_commit[:12]}")
            PrettyOutput.auto_print(f"Current HEAD commit:    {current_commit[:12]}")
            PrettyOutput.auto_print("")
            PrettyOutput.auto_print("The code state may be inconsistent with when the session was saved, which may cause:")
            PrettyOutput.auto_print("  • Missing code context")
            PrettyOutput.auto_print("  • Referenced files or functions do not exist")
            PrettyOutput.auto_print("  • Code references in the historical conversation become invalid")
            PrettyOutput.auto_print("")

            # If in non-interactive mode, warn and continue directly
            if self.non_interactive:
                PrettyOutput.auto_print("🤖 Non-interactive mode: automatically continue restoring (state may be inconsistent)")
                return True

            # Interactive mode: ask the user
            while True:
                choice = get_single_line_input(
                    "Please choose an action: [1] Reset to the saved commit  [2] Continue restoring (may be inconsistent): "
                ).strip()

                if choice == "1":
                    # Execute git reset
                    PrettyOutput.auto_print(
                        f"Resetting to commit {saved_commit[:12]}..."
                    )
                    reset_result = subprocess.run(
                        ["git", "reset", "--hard", saved_commit],
                        capture_output=True,
                        text=True,
                    )

                    if reset_result.returncode == 0:
                        PrettyOutput.auto_print("✅ Successfully reset to the commit when the session was saved")
                        return True
                    else:
                        PrettyOutput.auto_print(f"❌ Reset failed: {reset_result.stderr}")
                        # Reset failed, ask whether to continue
                        cont = (
                            get_single_line_input("Still continue restoring the session? [y/N]: ")
                            .strip()
                            .lower()
                        )
                        if cont in ["y", "yes"]:
                            PrettyOutput.auto_print("⚠️  Continuing to restore the session (state may be inconsistent)")
                            return True
                        else:
                            return False

                elif choice == "2":
                    PrettyOutput.auto_print("⚠️  Continuing to restore the session (state may be inconsistent)")
                    return True

                else:
                    PrettyOutput.auto_print("❌ Invalid choice, please enter 1 or 2")

        except Exception as e:
            # An error occurred during the check, log a warning but continue restoring
            PrettyOutput.auto_print(f"⚠️  Error while checking commit consistency: {e}")
            return True

    def _recreate_platform_if_needed(self, session_file: str) -> bool:
        """If the session file contains platform_type, recreate the platform instance

        Args:
            session_file: Session file path

        Returns:
            bool: Whether the platform instance was recreated
        """
        import json
        from haijunbot.haijunbot_platform.registry import PlatformRegistry

        try:
            with open(session_file, "r", encoding="utf-8") as f:
                state = json.load(f)

            platform_type = state.get("platform_type")
            if not platform_type:
                # Old session files have no platform_type, skip
                return False

            # Recreate the platform instance using the latest llm_group configuration
            registry = PlatformRegistry()
            if platform_type == "smart":
                new_model = registry.get_smart_platform()
            elif platform_type == "cheap":
                new_model = registry.get_cheap_platform()
            else:
                new_model = registry.get_normal_platform()

            # Preserve the original settings
            new_model.set_suppress_output(self.model.suppress_output)
            new_model.agent = self.model.agent

            # Update SessionManager's model reference
            self.model = new_model
            # Update the Agent's model reference
            if self.agent:
                self.agent.model = new_model
                self.agent.session.model = new_model

            PrettyOutput.auto_print(
                f"✅ Recreated the platform instance based on platform_type: {platform_type}"
            )
            return True
        except FileNotFoundError:
            return False
        except Exception as e:
            PrettyOutput.auto_print(f"⚠️ Failed to recreate the platform instance: {e}, using the existing instance")
            return False

    def restore_session_from_file(
        self, session_file: str, session_name: Optional[str] = None
    ) -> bool:
        """Restore the session state from the specified session file (unified restore entry point)

        This method encapsulates the complete restore logic and checks, including:
        - Commit consistency check
        - Platform instance recreation
        - Token compatibility check
        - Session state restoration

        Args:
            session_file: Session file path
            session_name: Session name (optional, used to set current_session_name)

        Returns:
            bool: Whether the restore succeeded
        """
        # Check commit consistency
        if not self._check_commit_consistency(session_file):
            PrettyOutput.auto_print("⏸️  Session restore canceled.")
            return False

        # Recreate the platform instance (if needed)
        self._recreate_platform_if_needed(session_file)

        # Check token compatibility before restoring the session
        if not self._check_token_compatibility_before_restore(session_file):
            PrettyOutput.auto_print(
                "❌ Session restore failed: the token count of the historical messages exceeds the current model's limit."
            )
            return False

        # Restore the session messages to the model
        if not self.model.restore(session_file):
            PrettyOutput.auto_print("❌ Session restore failed.")
            return False

        # Update the session info
        self.last_restored_session = session_file
        if session_name:
            self.current_session_name = session_name
        else:
            # Try to read the name from the session file
            self.current_session_name = self._read_session_name(session_file)

        # Restore the Agent runtime state
        self._restore_agent_state()

        # Restore the task lists
        self._restore_task_lists()

        # If it is a CodeAgent, restore the start_commit info
        self._restore_start_commit_info()

        # Print the most recent conversation turns so the user can confirm the restore is correct
        self._print_recent_conversation(session_file)

        return True

    def _print_recent_conversation(self, session_file: str, count: int = 4) -> None:
        """After restoring the session, print the most recent conversation turns so the user can confirm the restore is correct.

        Args:
            session_file: Session file path
            count: Number of most recent conversation messages to print
        """
        try:
            with open(session_file, "r", encoding="utf-8") as f:
                state = json.load(f)
            messages = state.get("messages", [])

            # Filter out the actual conversation messages (user questions and assistant text replies),
            # skip tool calls/results and system messages
            dialog = []
            for msg in messages:
                role = msg.get("role")
                content = msg.get("content")
                if not content:
                    continue
                if role == "user" and not msg.get("tool_call_id"):
                    dialog.append(("👤 User", content))
                elif role == "assistant":
                    dialog.append(("🤖 Assistant", content))

            if not dialog:
                return

            # Merge into a single Markdown message (blockquote) to avoid splitting into multiple for better readability
            lines = []
            for label, content in dialog[-count:]:
                # Truncate overly long content to avoid flooding the screen
                text = content.strip()
                if len(text) > 200:
                    text = text[:200] + "…"
                # Replace newlines in the content with spaces to keep the blockquote a single line
                text = text.replace("\n", " ")
                lines.append(f"> {label}: {text}")
            PrettyOutput.print_markdown(
                "\n".join(lines),
                title="📜 Recent conversation (for confirming the restore is correct)",
            )
        except Exception as e:
            PrettyOutput.auto_print(f"⚠️ Failed to print recent conversation: {e}")

    def _check_token_compatibility_before_restore(self, session_file: str) -> bool:
        """Check whether the token count of the historical messages meets the requirement before restoring the session

        This method reads messages directly from the session file and computes tokens, independent of the restored model state

        Args:
            session_file: Session file path

        Returns:
            bool: True if the token count meets the requirement, otherwise False
        """
        try:
            import json
            from haijunbot.haijunbot_utils.embedding import get_context_token_count

            # Get the maximum input token count of the current model
            max_input_tokens = self.model._get_platform_max_input_token_count()

            # Read messages from the session file
            with open(session_file, "r", encoding="utf-8") as f:
                state = json.load(f)

            messages = state.get("messages", [])

            # Compute the token count of the historical messages
            used_tokens = 0
            for message in messages:
                content = message.get("content", "")
                if content:
                    used_tokens += get_context_token_count(content)

            PrettyOutput.auto_print(
                f"📊 Session token stats: used {used_tokens}, max limit {max_input_tokens}"
            )

            # If the token count of the historical messages exceeds the model's maximum input limit, it is incompatible
            if used_tokens > max_input_tokens:
                PrettyOutput.auto_print(
                    f"⚠️  Current session token count ({used_tokens}) exceeds the model limit ({max_input_tokens})"
                )
                return False

            # A safety margin can be set, e.g. reserve 10% of the token space for new messages
            safety_margin = int(max_input_tokens * 0.1)
            if used_tokens > max_input_tokens - safety_margin:
                PrettyOutput.auto_print(
                    "⚠️  Current session token count is close to the model limit, history compression is recommended"
                )
                # Although close to the limit, it is still within range, return True

            return True
        except Exception as e:
            PrettyOutput.auto_print(f"⚠️  Failed to check token compatibility: {e}")
            # On error, still allow the restore for safety
            return True

    def restore_session(self) -> bool:
        """Restores the session state from a file."""
        sessions = self._parse_session_files()

        if not sessions:
            PrettyOutput.auto_print("❌ No restorable session file found.")
            return False

        # If there is only one session file, restore it directly
        if len(sessions) == 1:
            session_file, timestamp, session_name, commit_status = sessions[0]
            time_str = timestamp if timestamp else "(no timestamp)"
            name_str = f" [{session_name}]" if session_name else ""
            PrettyOutput.auto_print(
                f"📂 Restoring session{name_str}: {os.path.basename(session_file)} ({time_str})"
            )

            # Check commit consistency
            if not self._check_commit_consistency(session_file):
                PrettyOutput.auto_print("⏸️  Session restore canceled.")
                return False

            # Recreate the platform instance (if needed)
            self._recreate_platform_if_needed(session_file)

            # Check token compatibility before restoring the session
            if not self._check_token_compatibility_before_restore(session_file):
                PrettyOutput.auto_print(
                    "❌ Session restore failed: the token count of the historical messages exceeds the current model's limit."
                )
                return False

            if self.model.restore(session_file):
                self.last_restored_session = session_file  # Record the restored session file
                self.current_session_name = session_name  # Record the session name
                # Restore the Agent runtime state
                self._restore_agent_state()
                # Restore the task lists
                self._restore_task_lists()
                # If it is a CodeAgent, restore the start_commit info
                self._restore_start_commit_info()
                # Print the most recent conversation turns so the user can confirm the restore is correct
                self._print_recent_conversation(session_file)
                return True
            else:
                PrettyOutput.auto_print("❌ Session restore failed.")
                return False

        # Multiple session files, show a list for the user to choose
        # Check whether it is non-interactive mode
        if self.non_interactive:
            # Non-interactive mode: automatically restore the latest session
            session_file, timestamp, session_name, commit_status = sessions[0]
            time_str = timestamp if timestamp else "(no timestamp)"
            name_str = f" [{session_name}]" if session_name else ""
            PrettyOutput.auto_print(
                f"🤖 Non-interactive mode: automatically restoring the latest session{name_str}: {os.path.basename(session_file)} ({time_str})"
            )

            # Check commit consistency
            if not self._check_commit_consistency(session_file):
                PrettyOutput.auto_print("⏸️  Session restore canceled.")
                return False

            # Recreate the platform instance (if needed)
            self._recreate_platform_if_needed(session_file)

            # Check token compatibility before restoring the session
            if not self._check_token_compatibility_before_restore(session_file):
                PrettyOutput.auto_print(
                    "❌ Session restore failed: the token count of the historical messages exceeds the current model's limit."
                )
                return False

            if self.model.restore(session_file):
                self.last_restored_session = session_file  # Record the restored session file
                self.current_session_name = session_name  # Record the session name
                # Restore the Agent runtime state
                self._restore_agent_state()
                # Restore the task lists
                self._restore_task_lists()
                # If it is a CodeAgent, restore the start_commit info
                self._restore_start_commit_info()
                # Print the most recent conversation turns so the user can confirm the restore is correct
                self._print_recent_conversation(session_file)
                return True
            else:
                PrettyOutput.auto_print("❌ Session restore failed.")
                return False

        # Interactive mode: show a list for the user to choose
        session_list_text = "📋 Multiple session files found:\n"
        for idx, (file_path, timestamp, session_name, commit_status) in enumerate(
            sessions, 1
        ):
            time_str = timestamp if timestamp else "(no timestamp)"
            name_str = f" - {session_name}" if session_name else ""

            # Add a label based on the commit status
            commit_status_str = ""
            if commit_status == "consistent":
                commit_status_str = " [commit consistent]"
            elif commit_status == "inconsistent":
                commit_status_str = " [commit inconsistent]"
            elif commit_status == "no_commit":
                commit_status_str = " [no commit info]"

            session_list_text += f"  {idx}. {os.path.basename(file_path)} [{time_str}]{name_str}{commit_status_str}\n"
        # Add a cancel option
        session_list_text += "  0. Cancel restore"
        PrettyOutput.auto_print(session_list_text)

        try:
            while True:
                choice = get_single_line_input(
                    "Please choose the session to restore (enter a number, press Enter to cancel): "
                ).strip()

                # Pressing Enter directly or entering 0 cancels the restore
                if not choice or choice == "0":
                    return False

                if not choice.isdigit():
                    PrettyOutput.auto_print("❌ Invalid choice, please enter a number.")
                    continue

                choice_idx = int(choice) - 1

                if choice_idx < 0 or choice_idx >= len(sessions):
                    PrettyOutput.auto_print(
                        f"❌ Invalid choice, please enter a number between 1 and {len(sessions)}."
                    )
                    continue

                # Input is valid, break out of the loop
                break

            # Restore the selected session
            session_file, timestamp, session_name, commit_status = sessions[choice_idx]
            time_str = timestamp if timestamp else "(no timestamp)"
            name_str = f" [{session_name}]" if session_name else ""
            PrettyOutput.auto_print(
                f"📂 Restoring session{name_str}: {os.path.basename(session_file)} ({time_str})"
            )

            # Check commit consistency
            if not self._check_commit_consistency(session_file):
                PrettyOutput.auto_print("⏸️  Session restore canceled.")
                return False

            # Recreate the platform instance (if needed)
            self._recreate_platform_if_needed(session_file)

            # Check token compatibility before restoring the session
            if not self._check_token_compatibility_before_restore(session_file):
                PrettyOutput.auto_print(
                    "❌ Session restore failed: the token count of the historical messages exceeds the current model's limit."
                )
                return False

            if self.model.restore(session_file):
                self.last_restored_session = session_file  # Record the restored session file
                self.current_session_name = session_name  # Record the session name
                # Restore the Agent runtime state
                self._restore_agent_state()
                # Restore the task lists
                self._restore_task_lists()
                # If it is a CodeAgent, restore the start_commit info
                self._restore_start_commit_info()
                # Print the most recent conversation turns so the user can confirm the restore is correct
                self._print_recent_conversation(session_file)
                return True
            else:
                PrettyOutput.auto_print("❌ Session restore failed.")
                return False

        except (EOFError, KeyboardInterrupt):
            PrettyOutput.auto_print("⚠️ User canceled restore.")
            return False

    def _get_session_file_prefix(self) -> str:
        """
        Generate the session file prefix (without suffix).

        Returns:
            str: Session file prefix, e.g. "saved_session_Jarvos"
        """
        import os

        session_dir = os.path.join(os.getcwd(), ".haijunbot", "sessions")
        os.makedirs(session_dir, exist_ok=True)

        # Use session_name as the prefix (if it exists)
        if self.current_session_name:
            # Extract the filename from session_name (remove special characters)
            import re

            safe_name = re.sub(
                r"[^\u4e00-\u9fa5a-zA-Z0-9_-]", "", self.current_session_name
            )
            if safe_name:
                return f"{safe_name}_saved_session_{self.agent_name}"

        return f"saved_session_{self.agent_name}"

    def _build_task_lists(self) -> Optional[Dict[str, Any]]:
        """Construct in memory the contents of _tasklist.json (without writing to disk).

        Returns:
            Task list data dict; returns None if there is no task list or construction fails.
        """
        try:
            # Check whether the agent and task_list_manager exist
            if not self.agent:
                return None
            if (
                not hasattr(self.agent, "task_list_manager")
                or not self.agent.task_list_manager.task_lists
            ):
                return None  # No task list

            # Collect all task list data
            task_lists_data = {}
            for (
                task_list_id,
                task_list,
            ) in self.agent.task_list_manager.task_lists.items():
                task_lists_data[task_list_id] = task_list.to_dict()

            # Also save the task manager's global state to avoid ID conflicts after restore
            from haijunbot.haijunbot_agent.task_list import TaskListManager

            manager_state = {
                "global_task_counter": TaskListManager._global_task_counter,
                "global_tasklist_counter": TaskListManager._global_tasklist_counter,
            }

            return {
                "task_lists": task_lists_data,
                "manager_state": manager_state,
            }
        except Exception as e:
            PrettyOutput.auto_print(f"⚠️ Failed to save task lists: {e}")
            return None

    def _save_task_lists(self) -> bool:
        """Save the current Agent's task lists to a file.

        File naming rule: {prefix}_tasklist.json
        Saved in the same directory as the session file for easy association.

        Returns:
            bool: Whether the save succeeded
        """

        import os

        try:
            tasklist_data = self._build_task_lists()
            if tasklist_data is None:
                return True  # No task list, treat as success

            # Build the file path
            session_dir = os.path.join(os.getcwd(), ".haijunbot", "sessions")
            os.makedirs(session_dir, exist_ok=True)

            prefix = self._get_session_file_prefix()
            tasklist_file = os.path.join(session_dir, f"{prefix}_tasklist.json")

            # Save to file
            atomic_write_json(
                tasklist_file,
                tasklist_data,
                ensure_ascii=False,
                indent=2,
            )

            return True
        except Exception as e:
            PrettyOutput.auto_print(f"⚠️ Failed to save task lists: {e}")
            return False

    def _restore_task_lists(self) -> bool:
        """Restore the current Agent's task lists from a file.

        File naming rule: {prefix}_tasklist.json
        Saved in the same directory as the session file for easy association.

        Returns:
            bool: Whether the restore succeeded
        """
        import json
        import os
        import re

        try:
            if not self.agent:
                return True

            # Build the file path
            session_dir = os.path.join(os.getcwd(), ".haijunbot", "sessions")
            prefix = self._get_session_file_prefix()
            tasklist_file = os.path.join(session_dir, f"{prefix}_tasklist.json")

            if not os.path.exists(tasklist_file):
                return True  # File does not exist, treat as success (no task lists to restore)

            # Load the task list data from the file
            with open(tasklist_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            task_lists_data = data.get("task_lists", {})
            manager_state = data.get("manager_state", {})

            # Import TaskList and TaskListManager (avoid circular import)
            from haijunbot.haijunbot_agent.task_list import TaskList, TaskListManager

            # Clear the current task lists, then restore from the file
            self.agent.task_list_manager.task_lists.clear()

            # Restore the task lists one by one
            for task_list_id, task_list_data in task_lists_data.items():
                task_list = TaskList.from_dict(task_list_data)
                self.agent.task_list_manager.task_lists[task_list_id] = task_list

            # Restore the task ID/task list ID counters; for old-format files, derive a safe lower bound from the existing data
            inferred_task_counter = 0
            inferred_tasklist_counter = 0

            for (
                task_list_id,
                task_list,
            ) in self.agent.task_list_manager.task_lists.items():
                match = re.fullmatch(r"tasklist-(\d+)", str(task_list_id))
                if match:
                    inferred_tasklist_counter = max(
                        inferred_tasklist_counter, int(match.group(1))
                    )

                for task_id in task_list.tasks.keys():
                    match = re.fullmatch(r"task-(\d+)", str(task_id))
                    if match:
                        inferred_task_counter = max(
                            inferred_task_counter, int(match.group(1))
                        )

            saved_task_counter = int(manager_state.get("global_task_counter", 0) or 0)
            saved_tasklist_counter = int(
                manager_state.get("global_tasklist_counter", 0) or 0
            )

            TaskListManager._global_task_counter = max(
                TaskListManager._global_task_counter,
                saved_task_counter,
                inferred_task_counter,
            )
            TaskListManager._global_tasklist_counter = max(
                TaskListManager._global_tasklist_counter,
                saved_tasklist_counter,
                inferred_tasklist_counter,
            )

            return True
        except Exception as e:
            PrettyOutput.auto_print(f"⚠️ Failed to restore task lists: {e}")
            return False

    def _build_agent_state(self, timestamp: str) -> Optional[Dict[str, Any]]:
        """Construct in memory the contents of _state.json (without writing to disk).

        Args:
            timestamp: Session timestamp, used for the metadata record

        Returns:
            State data dict; returns None if there is no agent.
        """
        if not self.agent:
            return None

        # Save short-term memories
        short_term_memories = []
        try:
            from haijunbot.haijunbot_utils.globals import get_short_term_memories

            short_term_memories = get_short_term_memories()
        except Exception as e:
            PrettyOutput.auto_print(f"⚠️ Failed to get short-term memories: {e}")

        # Build the state data to be saved
        state_data: Dict[str, Any] = {
            "short_term_memories": short_term_memories,
            "session_manager": {
                "prompt": self.prompt,
                "user_data": self.user_data,
                "addon_prompt": self.addon_prompt,
                "conversation_length": self.conversation_length,
                "non_interactive": self.non_interactive,
            },
            "agent_runtime": {
                "addon_prompt_skip_rounds": getattr(
                    self.agent, "_addon_prompt_skip_rounds", 0
                ),
                "no_tool_call_count": getattr(self.agent, "_no_tool_call_count", 0),
                "last_response_content": getattr(
                    self.agent, "_last_response_content", ""
                ),
                "recent_memories": getattr(self.agent, "recent_memories", []),
                "MAX_RECENT_MEMORIES": getattr(self.agent, "MAX_RECENT_MEMORIES", 10),
                "memory_tags": list(getattr(self.agent, "memory_tags", set())),
                "first": getattr(self.agent, "first", True),
                "pin_content": getattr(self.agent, "pin_content", ""),
                "pre_compressed_summary": getattr(
                    self.agent, "_pre_compressed_summary", None
                ),
                "pre_compressing": getattr(self.agent, "_pre_compressing", False),
                "pre_compress_snapshot_count": getattr(
                    self.agent, "_pre_compress_snapshot_count", 0
                ),
            },
            "metadata": {
                "agent_name": self.agent_name,
                "timestamp": timestamp,
            },
        }

        # If it is a CodeAgent, additionally save CodeAgent-specific state
        if hasattr(self.agent, "start_commit"):
            state_data["code_agent"] = {
                "disable_review": getattr(self.agent, "disable_review", False),
                "review_max_iterations": getattr(
                    self.agent, "review_max_iterations", 3
                ),
                "tool_group": getattr(self.agent, "tool_group", "default"),
                "root_dir": getattr(self.agent, "root_dir", os.getcwd()),
                "prefix": getattr(self.agent, "prefix", ""),
                "suffix": getattr(self.agent, "suffix", ""),
            }

        # Save the RulesManager state (list of activated rules)
        if hasattr(self.agent, "rules_manager") and self.agent.rules_manager:
            state_data["rules_manager"] = {
                "loaded_rules": list(
                    getattr(self.agent.rules_manager, "loaded_rules", set())
                ),
                "active_rules": list(
                    getattr(self.agent.rules_manager, "_active_rules", set())
                ),
                # Added: save dynamically loaded rule content
                "loaded_rules_content": getattr(
                    self.agent.rules_manager, "_loaded_rules", {}
                ),
            }

        # Save the Timer state
        try:
            from haijunbot.haijunbot_tools.timer import get_timer_manager

            timer_manager = get_timer_manager()
            timer_state = timer_manager.get_state()
            if timer_state.get("tasks"):
                state_data["timer"] = timer_state
        except Exception as e:
            PrettyOutput.auto_print(f"⚠ Failed to save timer state: {e}")

        return state_data

    def _save_agent_state(self, timestamp: str) -> None:
        """Save the SessionManager and Agent runtime state to a file.

        Args:
            timestamp: Session timestamp, used to generate the filename
        """
        import os

        if not self.agent:
            return

        state_data = self._build_agent_state(timestamp)
        if state_data is None:
            return

        session_dir = os.path.join(os.getcwd(), ".haijunbot", "sessions")
        os.makedirs(session_dir, exist_ok=True)

        prefix = self._get_session_file_prefix()
        state_file = os.path.join(
            session_dir,
            f"{prefix}_{timestamp}_state.json",
        )

        # Import SafeEncoder (avoid circular import)
        from haijunbot.haijunbot_agent import SafeEncoder

        try:
            atomic_write_json(
                state_file,
                state_data,
                ensure_ascii=False,
                indent=2,
                default=SafeEncoder().default,
            )
            PrettyOutput.auto_print("✅ Agent state saved")
        except Exception as e:
            PrettyOutput.auto_print(f"⚠️ Failed to save Agent state: {e}")

    def _restore_agent_state(self) -> None:
        """Restore the SessionManager and Agent runtime state from a file."""
        import json
        import os

        if not self.agent:
            return

        try:
            # Extract the timestamp
            if not self.last_restored_session:
                return

            # Restore short-term memories
            restored_short_term_count = 0
            try:
                session_file = os.path.basename(self.last_restored_session)
                timestamp = self._extract_timestamp(session_file)

                if not timestamp:
                    PrettyOutput.auto_print("ℹ️ Session file has no timestamp, skipping short-term memory restore")
                else:
                    # Build the state file path
                    session_dir = os.path.join(os.getcwd(), ".haijunbot", "sessions")
                    prefix = self._get_session_file_prefix()
                    state_file = os.path.join(
                        session_dir,
                        f"{prefix}_{timestamp}_state.json",
                    )

                    if os.path.exists(state_file):
                        with open(state_file, "r", encoding="utf-8") as f:
                            state_data = json.load(f)

                        short_term_memories = state_data.get("short_term_memories", [])
                        if short_term_memories:
                            from haijunbot.haijunbot_utils.globals import (
                                add_short_term_memory,
                            )

                            for memory_data in short_term_memories:
                                try:
                                    add_short_term_memory(memory_data)
                                    restored_short_term_count += 1
                                except Exception as e:
                                    PrettyOutput.auto_print(f"⚠️ Failed to restore short-term memory: {e}")

                            if restored_short_term_count > 0:
                                PrettyOutput.auto_print(
                                    f"💾 Restored {restored_short_term_count} short-term memories"
                                )
                            else:
                                PrettyOutput.auto_print("💾 No short-term memories to restore")
                        else:
                            PrettyOutput.auto_print("💾 No short-term memories to restore")
            except Exception as e:
                PrettyOutput.auto_print(f"⚠️ Failed to restore short-term memory: {e}")

            session_file = os.path.basename(self.last_restored_session)
            timestamp = self._extract_timestamp(session_file)

            if not timestamp:
                PrettyOutput.auto_print("ℹ️ Session file has no timestamp, skipping state restore")
                return

            # Build the state file path
            session_dir = os.path.join(os.getcwd(), ".haijunbot", "sessions")
            prefix = self._get_session_file_prefix()
            state_file = os.path.join(
                session_dir,
                f"{prefix}_{timestamp}_state.json",
            )

            if not os.path.exists(state_file):
                PrettyOutput.auto_print("ℹ️ State file not found, skipping state restore")
                return

            # Load the state data from the file
            with open(state_file, "r", encoding="utf-8") as f:
                state_data = json.load(f)

            # Note: short-term memories were already restored at the beginning of the file, so they are not handled again here

            # Restore the SessionManager state
            session_manager_state = state_data.get("session_manager", {})
            if session_manager_state:
                self.prompt = session_manager_state.get("prompt", "")
                self.user_data = session_manager_state.get("user_data", {})
                self.addon_prompt = session_manager_state.get("addon_prompt", "")
                self.conversation_length = session_manager_state.get(
                    "conversation_length", 0
                )
                self.non_interactive = session_manager_state.get(
                    "non_interactive", False
                )
                PrettyOutput.auto_print("✅ SessionManager state restored")

            # Restore the Agent runtime state
            agent_runtime_state = state_data.get("agent_runtime", {})
            # After restoring the session, set the first flag to False to avoid repeating the first-run initialization
            self.agent.first = False
            if agent_runtime_state:
                # Restore the recent memories queue
                self.agent.recent_memories = agent_runtime_state.get(
                    "recent_memories", []
                )
                self.agent.MAX_RECENT_MEMORIES = agent_runtime_state.get(
                    "MAX_RECENT_MEMORIES", 10
                )
                # Restore memory tags
                memory_tags = agent_runtime_state.get("memory_tags", [])
                if memory_tags:
                    self.agent.memory_tags = set(memory_tags)
                # Restore Pin content
                pin_content = agent_runtime_state.get("pin_content", "")
                if pin_content:
                    self.agent.pin_content = pin_content
                    PrettyOutput.auto_print(f"✅ Restored pinned content: {pin_content[:50]}...")

                # Restore the pre-compression state
                pre_compressed_summary = agent_runtime_state.get(
                    "pre_compressed_summary", None
                )
                if pre_compressed_summary:
                    self.agent._pre_compressed_summary = pre_compressed_summary
                    # Compression is already done, no need to re-run pre-compression after restore
                    self.agent._pre_compressing = False
                else:
                    self.agent._pre_compressed_summary = None
                    # If compression was in progress at save time, restart pre-compression after restore
                    was_pre_compressing = agent_runtime_state.get(
                        "pre_compressing", False
                    )
                    self.agent._pre_compressing = False
                    if was_pre_compressing:
                        # Restart background pre-compression
                        self.agent._start_background_pre_compression()

                self.agent._pre_compress_snapshot_count = agent_runtime_state.get(
                    "pre_compress_snapshot_count", 0
                )

                PrettyOutput.auto_print("✅ Agent runtime state restored")

            # Restore CodeAgent-specific state
            if hasattr(self.agent, "start_commit"):
                code_agent_state = state_data.get("code_agent", {}) or state_data.get(
                    "codeagent", {}
                )  # Compatible with old format
                if code_agent_state:
                    self.agent.disable_review = code_agent_state.get(
                        "disable_review", False
                    )
                    self.agent.review_max_iterations = code_agent_state.get(
                        "review_max_iterations", 3
                    )
                    self.agent.tool_group = code_agent_state.get(
                        "tool_group", "default"
                    )
                    self.agent.root_dir = code_agent_state.get("root_dir", os.getcwd())
                    self.agent.prefix = code_agent_state.get("prefix", "")
                    self.agent.suffix = code_agent_state.get("suffix", "")
                    PrettyOutput.auto_print("✅ CodeAgent configuration restored")

            # Restore the RulesManager state (activated rules)
            if hasattr(self.agent, "rules_manager") and self.agent.rules_manager:
                rules_manager_state = state_data.get("rules_manager", {})
                if rules_manager_state:
                    # Restore dynamically loaded rule content
                    loaded_rules_content = rules_manager_state.get(
                        "loaded_rules_content", {}
                    )
                    if loaded_rules_content:
                        self.agent.rules_manager._loaded_rules.update(
                            loaded_rules_content
                        )
                        PrettyOutput.auto_print(
                            f"✅ Restored {len(loaded_rules_content)} dynamically loaded rule contents"
                        )

                    # loaded_rules = rules_manager_state.get("loaded_rules", [])  # Unused, kept for future reference
                    active_rules = rules_manager_state.get("active_rules", [])

                    # Reload the rules
                    reactivated_count = 0
                    for rule_name in active_rules:
                        try:
                            if hasattr(self.agent.rules_manager, "load_rule"):
                                self.agent.rules_manager.load_rule(rule_name)
                                reactivated_count += 1
                        except Exception:
                            pass  # The rule may no longer exist, fail silently

                    if reactivated_count > 0:
                        rule_names = ", ".join(active_rules)
                        PrettyOutput.auto_print(
                            f"✅ Reactivated {reactivated_count} rules: {rule_names}"
                        )

            # Restore the Timer state
            timer_state = state_data.get("timer")
            if timer_state:
                try:
                    from haijunbot.haijunbot_tools.timer import get_timer_manager

                    timer_manager = get_timer_manager()
                    timer_manager.restore_state(timer_state)
                except Exception as e:
                    PrettyOutput.auto_print(f"⚠ Failed to restore timer state: {e}")

        except Exception as e:
            PrettyOutput.auto_print(f"⚠️ Failed to restore Agent state: {e}")

    def _restore_start_commit_info(self) -> None:
        """Restore the CodeAgent's start_commit info."""
        import json
        import os

        if not self.agent:
            return

        # Only handle CodeAgent (which has the start_commit attribute)
        if not hasattr(self.agent, "start_commit"):
            return

        if not self.last_restored_session:
            return

        try:
            # Use the _extract_timestamp method to extract the timestamp
            session_file = os.path.basename(self.last_restored_session)
            timestamp = self._extract_timestamp(session_file)

            # Use _get_session_file_prefix() to get the correct prefix (containing session_name)
            prefix = self._get_session_file_prefix()

            # Determine the commit filename based on the timestamp
            if timestamp:
                # New format: includes the timestamp
                commit_filename = f"{prefix}_{timestamp}_commit.json"
            else:
                # Old format: does not include the timestamp
                commit_filename = f"{prefix}_commit.json"

            session_dir = os.path.join(os.getcwd(), ".haijunbot", "sessions")
            commit_file = os.path.join(session_dir, commit_filename)

            if os.path.exists(commit_file):
                with open(commit_file, "r", encoding="utf-8") as f:
                    commit_data = json.load(f)

                    # Get the saved commit info
                    saved_start_commit = commit_data.get("start_commit")
                    saved_last_backup_commit = commit_data.get("last_backup_commit")
                    saved_current_commit = commit_data.get("current_commit")

                    # Get the current latest commit
                    from haijunbot.haijunbot_utils.git_utils import get_latest_commit_hash

                    current_commit = get_latest_commit_hash()

                    # Verify: compare the saved current_commit with the current current_commit
                    # If they differ, the repository state has changed (new commits, reset, rebase, etc.)
                    if saved_current_commit and saved_current_commit != current_commit:
                        # Repository state has changed, ignore the saved start_commit and use the current latest commit
                        self.agent.start_commit = current_commit
                        PrettyOutput.auto_print(
                            f"⚠️ Repository state change detected (at save time: {saved_current_commit[:8]}..., now: {current_commit[:8] if current_commit else 'None'}...), "
                            f"ignoring the saved start_commit and updating to the current commit"
                        )
                    elif saved_start_commit:
                        # Repository state unchanged, we can restore the saved start_commit
                        self.agent.start_commit = saved_start_commit
                        # Also restore last_backup_commit (if present and the agent supports it)
                        if saved_last_backup_commit and hasattr(
                            self.agent, "last_backup_commit"
                        ):
                            self.agent.last_backup_commit = saved_last_backup_commit
                        PrettyOutput.auto_print(
                            f"✅ Restored start_commit info: {self.agent.start_commit[:8] if self.agent.start_commit else 'None'}..."
                        )
                        if saved_last_backup_commit:
                            PrettyOutput.auto_print(
                                f"✅ Restored last_backup_commit info: {saved_last_backup_commit[:8]}..."
                            )
                    else:
                        # No saved start_commit, use the current latest commit
                        self.agent.start_commit = current_commit
                        PrettyOutput.auto_print(
                            f"✅ Set start_commit to the current commit: {current_commit[:8] if current_commit else 'None'}..."
                        )
            else:
                PrettyOutput.auto_print(f"ℹ️ Corresponding commit file not found: {commit_filename}")
        except Exception as e:
            PrettyOutput.auto_print(f"⚠️ Failed to restore commit info: {e}")

    def clear_history(self) -> None:
        """
        Clears conversation history but keeps the system prompt by resetting the model state.
        """
        self.prompt = ""
        self.conversation_length = 0
        self.model.reset()

    def clear(self) -> None:
        """
        Clears the session state, resetting prompt and conversation length while
        preserving user_data. This method is an alias of clear_history for backward
        compatibility with existing tests and callers.
        """
        self.clear_history()
