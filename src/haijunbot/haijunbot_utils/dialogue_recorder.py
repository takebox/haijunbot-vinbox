#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Dialogue recorder module

Provides dialogue recording and management features, supporting multiple sessions, JSONL format storage, automatic cleanup, and more.
"""

from haijunbot.haijunbot_utils.exception_utils import save_exception
import atexit
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any
from typing import Dict
from typing import List
from typing import Optional

from .config import get_data_dir

# Global instance variable
_global_recorder: Optional["DialogueRecorder"] = None


class DialogueRecorder:
    """Dialogue recorder class

    Used to record and manage dialogue history, supporting multiple sessions and JSONL format storage.

    Features:
    - Automatically generates session IDs
    - JSONL format storage, one message record per line
    - Supports metadata extension
    - Automatically cleans up old sessions
    - Process-safe file writing
    """

    def __init__(self, session_id: Optional[str] = None):
        """Initialize the dialogue recorder

        Args:
            session_id: Session ID; if None, the current session ID is used
        """
        self.data_dir = Path(get_data_dir()) / "dialogues"
        self._session_id_cache: Optional[str] = None
        self.session_id = session_id or self._get_current_session_id()
        self._ensure_data_dir()
        self._register_cleanup_hook()

    def __del__(self) -> None:
        """Destructor, ensuring resources are cleaned up"""
        if hasattr(self, "_cleanup_registered"):
            self._unregister_cleanup_hook()

    def start_recording(self) -> str:
        """Start a new dialogue recording

        Returns:
            str: The newly generated session ID
        """
        new_session_id = str(uuid.uuid4())
        return new_session_id

    def record_message(
        self, role: str, content: str, metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Record a message

        Args:
            role: Message role (such as 'user', 'assistant', 'system')
            content: Message content
            metadata: Optional metadata
        """
        record = {
            "timestamp": datetime.now().isoformat(),
            "role": role,
            "content": content,
            "metadata": metadata or {},
        }
        self._write_record(record)

    def get_session_file_path(self) -> str:
        """Get the current session file path

        Returns:
            str: The full path of the current session file
        """
        return str(self._get_session_path(self.session_id))

    def get_all_sessions(self) -> List[str]:
        """Get a list of all session IDs

        Returns:
            List[str]: A list of all session IDs
        """
        if not self.data_dir.exists():
            return []

        session_files = self.data_dir.glob("*.jsonl")
        sessions = []
        for file_path in session_files:
            session_id = file_path.stem
            if file_path.is_file() and session_id:
                sessions.append(session_id)

        return sorted(sessions)

    def read_session(self, session_id: str) -> List[Dict[str, Any]]:
        """Read the content of the specified session

        Args:
            session_id: Session ID

        Returns:
            List[Dict[str, Any]]: The list of session messages
        """
        file_path = self._get_session_path(session_id)
        if not file_path.exists():
            return []

        messages = []
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            message = json.loads(line)
                            messages.append(message)
                        except json.JSONDecodeError:
                            continue
        except Exception as e:
            save_exception(
                e, module="haijunbot_utils.dialogue_recorder", function="read_session"
            )
            pass
        return messages

    def cleanup_session(self, session_id: Optional[str] = None) -> None:
        """Clean up the specified session file

        Args:
            session_id: Session ID; if None, the current session is cleaned up
        """
        session_to_cleanup = session_id or self.session_id
        file_path = self._get_session_path(session_to_cleanup)

        if file_path.exists():
            try:
                file_path.unlink()
            except Exception as e:
                save_exception(
                    e,
                    module="haijunbot_utils.dialogue_recorder",
                    function="cleanup_session",
                )
                pass

    def cleanup_all_sessions(self) -> None:
        """Clean up all session files"""
        if not self.data_dir.exists():
            return

        session_files = list(self.data_dir.glob("*.jsonl"))
        if not session_files:
            return

        for file_path in session_files:
            try:
                file_path.unlink()
            except Exception as e:
                save_exception(
                    e,
                    module="haijunbot_utils.dialogue_recorder",
                    function="cleanup_all_sessions",
                )
                pass

    def get_session_count(self) -> int:
        """Get the total number of sessions

        Returns:
            int: The total number of sessions
        """
        return len(self.get_all_sessions())

    def _ensure_data_dir(self) -> None:
        """Ensure the data directory exists"""
        try:
            self.data_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            save_exception(
                e, module="haijunbot_utils.dialogue_recorder", function="_ensure_data_dir"
            )
            pass

    def _get_current_session_id(self) -> str:
        """Get the current session ID"""
        # Get the current session ID from an environment variable or configuration
        # If there is none, generate a new one
        if self._session_id_cache is not None:
            return self._session_id_cache

        # Check whether there are existing session files
        existing_sessions = self.get_all_sessions()
        if existing_sessions:
            # Use the latest session
            session_id = existing_sessions[-1]
            self._session_id_cache = session_id
            return session_id

        # Generate a new session ID
        new_session_id = str(uuid.uuid4())
        self._session_id_cache = new_session_id
        return new_session_id

    def _write_record(self, record: Dict[str, Any]) -> None:
        """Write a single record to the file"""
        file_path = self._get_session_path(self.session_id)

        try:
            with open(file_path, "a", encoding="utf-8") as f:
                json.dump(record, f, ensure_ascii=False)
                f.write("\n")
        except Exception as e:
            save_exception(
                e, module="haijunbot_utils.dialogue_recorder", function="_write_record"
            )
            pass

    def _get_session_path(self, session_id: str) -> Path:
        """Get the session file path"""
        return self.data_dir / f"{session_id}.jsonl"

    def _register_cleanup_hook(self) -> None:
        """Register the atexit cleanup hook"""
        if not hasattr(self, "_cleanup_registered"):
            atexit.register(self._cleanup_on_exit)
            self._cleanup_registered = True

    def _unregister_cleanup_hook(self) -> None:
        """Unregister the atexit cleanup hook"""
        if hasattr(self, "_cleanup_registered"):
            try:
                atexit.unregister(self._cleanup_on_exit)
            except ValueError:
                # The hook may already be unregistered or never registered
                pass
            del self._cleanup_registered

    def _cleanup_on_exit(self) -> None:
        """Cleanup function on process exit

        Ensures the current session file is cleaned up on both normal and abnormal process exit
        """
        try:
            # Only clean up the current session to avoid affecting other sessions
            self.cleanup_session()
        except Exception:
            # Do not raise an exception on cleanup failure, to avoid affecting process exit
            pass


def get_global_recorder() -> DialogueRecorder:
    """Get the global singleton dialogue recorder

    Returns:
        DialogueRecorder: The global dialogue recorder instance
    """
    global _global_recorder
    if _global_recorder is None:
        _global_recorder = DialogueRecorder()
    return _global_recorder


def record_user_message(
    content: str, metadata: Optional[Dict[str, Any]] = None
) -> None:
    """Convenience function: record a user message

    Args:
        content: Message content
        metadata: Optional metadata
    """
    recorder = get_global_recorder()
    recorder.record_message("user", content, metadata)


def record_assistant_message(
    content: str, metadata: Optional[Dict[str, Any]] = None
) -> None:
    """Convenience function: record an assistant message

    Args:
        content: Message content
        metadata: Optional metadata
    """
    recorder = get_global_recorder()
    recorder.record_message("assistant", content, metadata)


def get_current_session_path() -> str:
    """Convenience function: get the current session file path

    Returns:
        str: The current session file path
    """
    recorder = get_global_recorder()
    return recorder.get_session_file_path()


# Automatically initialize and register the cleanup hook when the module is imported
_global_recorder = get_global_recorder()
